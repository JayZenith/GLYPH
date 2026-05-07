"""
TASK format validator.
Validates syntax and structure of generated traces.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tags_defined: set[str] = field(default_factory=set)
    tags_referenced: set[str] = field(default_factory=set)
    todos_defined: set[int] = field(default_factory=set)
    todos_satisfied: set[int] = field(default_factory=set)


class TaskValidator:
    """Validates TASK format traces."""

    # Structure patterns
    SYSTEM_PATTERN = re.compile(r'system「([^」]*)」(?:\s*🏷\s*(\S+))?')
    USER_PATTERN = re.compile(r'user「([^」]*)」(?:\s*🏷\s*(\S+))?')
    RESPONSE_PATTERN = re.compile(r'response「([^」]*)」')

    TOOL_BLOCK = re.compile(r'tool\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL)
    PLAN_BLOCK = re.compile(r'plan\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL)
    ACT_BLOCK = re.compile(r'act\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL)
    RESULT_BLOCK = re.compile(r'result\s*\{[^}]*\}', re.DOTALL)
    RESULT_BLOCK_BAD_TAG = re.compile(r'result\s*\{[^}]*\}\s*🏷', re.DOTALL)  # Tag on block (wrong)
    RESULT_DATA_TAG = re.compile(r'data\s*↦\s*["\「][^"」]*["\」]\s*🏷\s*(\S+)', re.DOTALL)  # Tag on data (correct)

    # Tool name pattern
    TOOL_NAME = re.compile(r'name\s*↦\s*([^\s•}]+)')

    # Operator patterns
    TAG_PATTERN = re.compile(r'🏷\s*["\']?([^"\'\s•\}]+)["\']?')
    REF_PATTERN = re.compile(r'※\s*(?:\[\s*([^\]]+)\s*\]|["\']?([^"\'\s•\}]+)["\']?)')
    SATISFIES_PATTERN = re.compile(r'⊨\s*(\d+)')
    CONFIDENCE_PATTERN = re.compile(r'𝑝\s*([\d.]+)')

    # Todo pattern
    TODO_ITEM_PATTERN = re.compile(r'(\d+)\s*↦\s*["\']([^"\']+)["\']')

    # Hardening patterns
    REPETITION_PATTERN = re.compile(r'(.{20,200}?)\1{4,}', re.DOTALL)
    # \bid — word boundary so "plan_id ↦ ..." doesn't match as an id field
    CALL_ID_PATTERN = re.compile(r'call\s*↦\s*\{[^}]*?\bid\s*↦\s*([\w\"\-]+)', re.DOTALL)
    RESULT_ID_PATTERN = re.compile(r'data\s*↦\s*[^🏷]*🏷\s*([\w\"\-]+)', re.DOTALL)
    TAIL_OK_PATTERN = re.compile(r'[\s※⊨𝑝🏷•\[\]\w\d\.\-\"\']*')
    # Strip chat template tokens (`<|im_end|>`, `<|im_start|>...`) before tail check
    CHAT_TEMPLATE_TOKEN = re.compile(r'<\|im_(?:start|end)\|>(?:\w*)?')

    def validate(self, trace: str) -> ValidationResult:
        """Validate a TASK format trace."""
        result = ValidationResult(valid=True)

        # Check basic structure exists
        self._check_structure(trace, result)

        # Extract and validate tags
        self._extract_tags(trace, result)

        # Extract and validate todos
        self._extract_todos(trace, result)

        # Check tag references
        self._check_references(result)

        # Check todo satisfaction
        self._check_todo_satisfaction(result)

        # Check confidence values
        self._check_confidence(trace, result)

        # Check bracket balance
        self._check_brackets(trace, result)

        # Check tool names
        self._check_tool_names(trace, result)

        # Check result tag placement
        self._check_result_tags(trace, result)

        # Hardening checks (now errors, not warnings)
        self._check_repetition(trace, result)
        self._check_termination(trace, result)
        self._check_call_result_pairing(trace, result)

        return result

    def _check_structure(self, trace: str, result: ValidationResult):
        """Check that required structures exist in correct order."""
        has_system = bool(self.SYSTEM_PATTERN.search(trace))
        has_user = bool(self.USER_PATTERN.search(trace))
        has_plan = bool(self.PLAN_BLOCK.search(trace))
        has_response = bool(self.RESPONSE_PATTERN.search(trace))

        if not has_system:
            result.errors.append("Missing system message")
            result.valid = False
        if not has_user:
            result.errors.append("Missing user message")
            result.valid = False
        if not has_plan:
            result.errors.append("Missing plan block")
            result.valid = False
        if not has_response:
            result.errors.append("Missing response")
            result.valid = False

        # Check order (rough check based on positions)
        if has_system and has_user:
            sys_pos = trace.find('system')
            user_pos = trace.find('user「')
            if user_pos < sys_pos:
                result.errors.append("User message appears before system message")
                result.valid = False

        if has_user and has_plan:
            user_pos = trace.find('user「')
            plan_pos = trace.find('plan {')
            if plan_pos != -1 and plan_pos < user_pos:
                result.errors.append("Plan appears before user message")
                result.valid = False

        if has_plan and has_response:
            plan_pos = trace.find('plan {')
            resp_pos = trace.find('response「')
            if plan_pos != -1 and resp_pos < plan_pos:
                result.errors.append("Response appears before plan")
                result.valid = False

    def _extract_tags(self, trace: str, result: ValidationResult):
        """Extract all defined tags."""
        # Tags from 🏷 operator (general)
        for match in self.TAG_PATTERN.finditer(trace):
            result.tags_defined.add(match.group(1))

        # Tags from result data expressions (correct placement)
        for match in self.RESULT_DATA_TAG.finditer(trace):
            result.tags_defined.add(match.group(1))

        # Extract referenced tags
        for match in self.REF_PATTERN.finditer(trace):
            if match.group(1):  # Array reference
                refs = match.group(1).split('•')
                for ref in refs:
                    ref = ref.strip().strip('"\'')
                    if ref:
                        result.tags_referenced.add(ref)
            elif match.group(2):  # Single reference
                result.tags_referenced.add(match.group(2))

    def _extract_todos(self, trace: str, result: ValidationResult):
        """Extract todo items and satisfaction markers."""
        # Find todos in plan blocks
        for plan_match in self.PLAN_BLOCK.finditer(trace):
            plan_content = plan_match.group(1)
            for todo_match in self.TODO_ITEM_PATTERN.finditer(plan_content):
                result.todos_defined.add(int(todo_match.group(1)))

        # Find satisfaction markers
        for match in self.SATISFIES_PATTERN.finditer(trace):
            result.todos_satisfied.add(int(match.group(1)))

    def _check_references(self, result: ValidationResult):
        """Check that all referenced tags are defined. Now an ERROR — broken refs poison RL signal."""
        undefined = result.tags_referenced - result.tags_defined
        if undefined:
            result.errors.append(f"References to undefined tags: {undefined}")
            result.valid = False

    def _check_todo_satisfaction(self, result: ValidationResult):
        """Check that all todos are satisfied. Unsatisfied todos = incomplete plan = ERROR."""
        unsatisfied = result.todos_defined - result.todos_satisfied
        if unsatisfied:
            result.errors.append(f"Unsatisfied todo items: {unsatisfied}")
            result.valid = False

        # Satisfaction of undefined todos stays a warning (less load-bearing)
        extra = result.todos_satisfied - result.todos_defined
        if extra:
            result.warnings.append(f"Satisfaction markers for undefined todos: {extra}")

    def _check_confidence(self, trace: str, result: ValidationResult):
        """Check confidence values are valid."""
        for match in self.CONFIDENCE_PATTERN.finditer(trace):
            try:
                conf = float(match.group(1))
                if not 0.0 <= conf <= 1.0:
                    result.warnings.append(f"Confidence value out of range: {conf}")
            except ValueError:
                result.errors.append(f"Invalid confidence value: {match.group(1)}")
                result.valid = False

    def _check_brackets(self, trace: str, result: ValidationResult):
        """Check bracket balance."""
        # Count { and }
        open_braces = trace.count('{')
        close_braces = trace.count('}')
        if open_braces != close_braces:
            result.errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
            result.valid = False

        # Count [ and ]
        open_brackets = trace.count('[')
        close_brackets = trace.count(']')
        if open_brackets != close_brackets:
            result.errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")
            result.valid = False

        # Count 「 and 」
        open_special = trace.count('「')
        close_special = trace.count('」')
        if open_special != close_special:
            result.errors.append(f"Unbalanced special quotes: {open_special} open, {close_special} close")
            result.valid = False

    def _check_tool_names(self, trace: str, result: ValidationResult):
        """Check that tool names don't contain spaces."""
        for match in self.TOOL_NAME.finditer(trace):
            name = match.group(1).strip('"\'')
            if ' ' in name:
                result.errors.append(f"Tool name contains spaces: '{name}' - use snake_case or camelCase")
                result.valid = False

    def _check_result_tags(self, trace: str, result: ValidationResult):
        """Check that result tags are on the data expression, not the block."""
        if self.RESULT_BLOCK_BAD_TAG.search(trace):
            result.warnings.append("Result block has tag on outside - tag should be on data expression inside")

    def _check_repetition(self, trace: str, result: ValidationResult):
        """Catch token-spam / mode collapse — 20-200 char chunk repeated 5+ times."""
        m = self.REPETITION_PATTERN.search(trace)
        if m:
            chunk = m.group(1)[:60]
            result.errors.append(f"Detected repetition (chunk repeats 5+ times): {chunk!r}")
            result.valid = False

    def _check_termination(self, trace: str, result: ValidationResult):
        """Trace must end with a response block — no garbage trailing tokens."""
        last_resp = trace.rfind('response「')
        last_close = trace.rfind('」')
        if last_resp < 0:
            return  # already caught by _check_structure
        if last_close <= last_resp:
            result.errors.append("Final response block is unclosed (no closing 」 after response「)")
            result.valid = False
            return
        tail = trace[last_close + 1:]
        # Strip chat template tokens (the trace SHOULD end with <|im_end|>)
        tail = self.CHAT_TEMPLATE_TOKEN.sub('', tail).strip()
        if tail and not self.TAIL_OK_PATTERN.fullmatch(tail):
            result.errors.append(f"Garbage after final response: {tail[:80]!r}")
            result.valid = False

    def _check_call_result_pairing(self, trace: str, result: ValidationResult):
        """Every tool call id must have a matching result tag."""
        call_ids = {c.strip('"') for c in self.CALL_ID_PATTERN.findall(trace)}
        result_ids = {r.strip('"') for r in self.RESULT_ID_PATTERN.findall(trace)}
        # Also accept ids tagged via the generic 🏷 operator
        result_ids |= result.tags_defined
        unmatched = call_ids - result_ids
        if unmatched:
            result.errors.append(f"Tool calls without matching result: {unmatched}")
            result.valid = False


def validate_trace(trace: str) -> ValidationResult:
    """Convenience function to validate a trace."""
    validator = TaskValidator()
    return validator.validate(trace)


if __name__ == "__main__":
    # Test with example
    example = '''system「You are a helpful assistant.」🏷 sys1

tool {
    name ↦ get_weather •
    description ↦ "Fetches current weather" •
    params ↦ {
        zip_code ↦ { type ↦ string • description ↦ "US ZIP code" }
    }
}

user「What is the weather?」🏷 usr1

plan {
    todo ↦ {
        1 ↦ "Get weather." •
        2 ↦ "Respond."
    } •
    rationale ↦ "Simple task."
}

act {
    call ↦ {
        tool ↦ get_weather •
        zip_code ↦ "94103" •
        id ↦ weather_result
    } ⊨ 1
}

result {
    data ↦ "68F, overcast." 🏷 weather_result
}

response「It's 68F and overcast.」※ weather_result ⊨ 2'''

    result = validate_trace(example)
    print(f"Valid: {result.valid}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    print(f"Tags defined: {result.tags_defined}")
    print(f"Tags referenced: {result.tags_referenced}")
    print(f"Todos defined: {result.todos_defined}")
    print(f"Todos satisfied: {result.todos_satisfied}")
