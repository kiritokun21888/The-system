"""Deterministic task catalog.

The offline ("deterministic") LLM backend uses this catalog so the *entire*
pipeline — including the TestRunner actually executing generated code — runs
end-to-end with no API key and fully reproducibly. Each entry provides:

  - ``detect``:     keywords that map a free-form prompt to this task.
  - ``spec``:       the structured specification the SpecParser "produces".
  - ``code``:       a correct reference implementation.
  - ``buggy_code``: an intentionally wrong first attempt (used when
                    ``buggy_first`` is set) so the test-fix feedback loop can be
                    demonstrated converging live.
  - ``tests``:      a test module (plain ``assert`` ``test_*`` functions) that
                    imports the implementation from ``solution``.
  - ``buggy_first``: if True, the deterministic Coder emits ``buggy_code`` on the
                    first attempt and ``code`` thereafter.

For the real Anthropic backend none of this is used — Claude generates the code.
"""

from __future__ import annotations

from typing import Any, Optional

CATALOG: dict[str, dict[str, Any]] = {
    "fibonacci": {
        "detect": ["fibonacci", "fib sequence", "nth fib"],
        "spec": {
            "function_name": "fibonacci",
            "signature": "def fibonacci(n: int) -> int",
            "description": "Return the n-th Fibonacci number (0-indexed).",
            "requirements": [
                "fibonacci(0) == 0 and fibonacci(1) == 1",
                "Raise ValueError for negative n",
                "Run in O(n) time and O(1) space",
            ],
            "examples": [
                {"input": 0, "output": 0},
                {"input": 10, "output": 55},
            ],
            "task_key": "fibonacci",
            "trivial": False,
        },
        "code": (
            "def fibonacci(n: int) -> int:\n"
            '    """Return the n-th Fibonacci number (0-indexed)."""\n'
            "    if n < 0:\n"
            '        raise ValueError("n must be non-negative")\n'
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n"
        ),
        "buggy_code": (
            "def fibonacci(n: int) -> int:\n"
            '    """Return the n-th Fibonacci number (0-indexed)."""\n'
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return b\n"  # off-by-one: returns b instead of a
        ),
        "tests": (
            "from solution import fibonacci\n\n"
            "def test_base_cases():\n"
            "    assert fibonacci(0) == 0\n"
            "    assert fibonacci(1) == 1\n\n"
            "def test_sequence():\n"
            "    assert fibonacci(10) == 55\n"
            "    assert fibonacci(7) == 13\n\n"
            "def test_negative_raises():\n"
            "    try:\n"
            "        fibonacci(-1)\n"
            "        assert False, 'expected ValueError'\n"
            "    except ValueError:\n"
            "        pass\n"
        ),
        "buggy_first": True,
    },
    "is_prime": {
        "detect": ["prime", "is_prime", "primality"],
        "spec": {
            "function_name": "is_prime",
            "signature": "def is_prime(n: int) -> bool",
            "description": "Return True if n is a prime number, else False.",
            "requirements": [
                "Numbers < 2 are not prime",
                "Handle 2 and 3 correctly",
                "Efficient trial division up to sqrt(n)",
            ],
            "examples": [
                {"input": 2, "output": True},
                {"input": 9, "output": False},
            ],
            "task_key": "is_prime",
            "trivial": False,
        },
        "code": (
            "def is_prime(n: int) -> bool:\n"
            '    """Return True if n is a prime number, else False."""\n'
            "    if n < 2:\n"
            "        return False\n"
            "    if n < 4:\n"
            "        return True\n"
            "    if n % 2 == 0:\n"
            "        return False\n"
            "    i = 3\n"
            "    while i * i <= n:\n"
            "        if n % i == 0:\n"
            "            return False\n"
            "        i += 2\n"
            "    return True\n"
        ),
        "buggy_code": "",  # not used: buggy_first is False
        "tests": (
            "from solution import is_prime\n\n"
            "def test_small():\n"
            "    assert is_prime(2) is True\n"
            "    assert is_prime(3) is True\n"
            "    assert is_prime(4) is False\n\n"
            "def test_composites_and_primes():\n"
            "    assert is_prime(9) is False\n"
            "    assert is_prime(13) is True\n"
            "    assert is_prime(1) is False\n"
            "    assert is_prime(97) is True\n"
        ),
        "buggy_first": False,
    },
    "factorial": {
        "detect": ["factorial"],
        "spec": {
            "function_name": "factorial",
            "signature": "def factorial(n: int) -> int",
            "description": "Return n! (the factorial of n).",
            "requirements": [
                "factorial(0) == 1",
                "Raise ValueError for negative n",
            ],
            "examples": [
                {"input": 0, "output": 1},
                {"input": 5, "output": 120},
            ],
            "task_key": "factorial",
            "trivial": True,
        },
        "code": (
            "def factorial(n: int) -> int:\n"
            '    """Return n! (the factorial of n)."""\n'
            "    if n < 0:\n"
            '        raise ValueError("n must be non-negative")\n'
            "    result = 1\n"
            "    for i in range(2, n + 1):\n"
            "        result *= i\n"
            "    return result\n"
        ),
        "buggy_code": "",
        "tests": (
            "from solution import factorial\n\n"
            "def test_base():\n"
            "    assert factorial(0) == 1\n"
            "    assert factorial(1) == 1\n\n"
            "def test_values():\n"
            "    assert factorial(5) == 120\n"
            "    assert factorial(6) == 720\n"
        ),
        "buggy_first": False,
    },
    "reverse_string": {
        "detect": ["reverse a string", "reverse string", "reverse_string"],
        "spec": {
            "function_name": "reverse_string",
            "signature": "def reverse_string(s: str) -> str",
            "description": "Return the reverse of string s.",
            "requirements": ["Empty string returns empty string"],
            "examples": [{"input": "abc", "output": "cba"}],
            "task_key": "reverse_string",
            "trivial": True,
        },
        "code": (
            "def reverse_string(s: str) -> str:\n"
            '    """Return the reverse of string s."""\n'
            "    return s[::-1]\n"
        ),
        "buggy_code": "",
        "tests": (
            "from solution import reverse_string\n\n"
            "def test_reverse():\n"
            "    assert reverse_string('abc') == 'cba'\n"
            "    assert reverse_string('') == ''\n"
            "    assert reverse_string('a') == 'a'\n"
        ),
        "buggy_first": False,
    },
    "palindrome": {
        "detect": ["palindrome"],
        "spec": {
            "function_name": "is_palindrome",
            "signature": "def is_palindrome(s: str) -> bool",
            "description": "Return True if s reads the same forwards and backwards, "
            "ignoring case and non-alphanumeric characters.",
            "requirements": [
                "Case-insensitive",
                "Ignore spaces and punctuation",
            ],
            "examples": [{"input": "A man a plan a canal Panama", "output": True}],
            "task_key": "palindrome",
            "trivial": False,
        },
        "code": (
            "def is_palindrome(s: str) -> bool:\n"
            '    """Return True if s is a palindrome (ignoring case/punctuation)."""\n'
            "    cleaned = [c.lower() for c in s if c.isalnum()]\n"
            "    return cleaned == cleaned[::-1]\n"
        ),
        "buggy_code": "",
        "tests": (
            "from solution import is_palindrome\n\n"
            "def test_palindromes():\n"
            "    assert is_palindrome('A man a plan a canal Panama') is True\n"
            "    assert is_palindrome('racecar') is True\n\n"
            "def test_non_palindromes():\n"
            "    assert is_palindrome('hello') is False\n"
        ),
        "buggy_first": False,
    },
    "gcd": {
        "detect": ["gcd", "greatest common divisor"],
        "spec": {
            "function_name": "gcd",
            "signature": "def gcd(a: int, b: int) -> int",
            "description": "Return the greatest common divisor of a and b.",
            "requirements": ["gcd(a, 0) == abs(a)", "Always non-negative result"],
            "examples": [{"input": [12, 18], "output": 6}],
            "task_key": "gcd",
            "trivial": True,
        },
        "code": (
            "def gcd(a: int, b: int) -> int:\n"
            '    """Return the greatest common divisor of a and b."""\n'
            "    while b:\n"
            "        a, b = b, a % b\n"
            "    return abs(a)\n"
        ),
        "buggy_code": "",
        "tests": (
            "from solution import gcd\n\n"
            "def test_gcd():\n"
            "    assert gcd(12, 18) == 6\n"
            "    assert gcd(17, 5) == 1\n"
            "    assert gcd(0, 9) == 9\n"
        ),
        "buggy_first": False,
    },
}


def detect_task_key(prompt: str) -> Optional[str]:
    """Map a free-form prompt to a catalog key via keyword matching.

    Args:
        prompt: The natural-language task description.

    Returns:
        The matching catalog key, or ``None`` if no entry matches.
    """
    low = prompt.lower()
    for key, entry in CATALOG.items():
        for kw in entry["detect"]:
            if kw in low:
                return key
    return None
