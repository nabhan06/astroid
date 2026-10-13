# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

import pytest

from astroid import bases, builder, nodes


def test_infer_typevar() -> None:
    """
    Regression test for: https://github.com/pylint-dev/pylint/issues/8802

    Test that an inferred `typing.TypeVar()` call produces a `nodes.ClassDef`
    node.
    """
    call_node = builder.extract_node("""
    from typing import TypeVar
    TypeVar('My.Type')
    """)
    inferred = next(call_node.infer())
    assert isinstance(inferred, nodes.ClassDef)
    assert inferred.name == "My.Type"


def test_infer_typevar_name_injection() -> None:
    """A crafted TypeVar name must not be spliced into the synthesized class."""
    call_node = builder.extract_node("""
    from typing import TypeVar
    TypeVar('T(EvilBase): #')
    """)
    inferred = next(call_node.infer())
    assert isinstance(inferred, nodes.ClassDef)
    # The name is kept verbatim instead of parsed, so no base is injected.
    assert inferred.name == "T(EvilBase): #"
    assert inferred.bases == []


class TestTypingAlias:
    def test_infer_typing_alias(self) -> None:
        """
        Test that _alias() calls can be inferred.
        """
        node = builder.extract_node("""
            from typing import _alias
            x = _alias(int, float)
            """)
        assert isinstance(node, nodes.Assign)
        assert isinstance(node.value, nodes.Call)
        inferred = next(node.value.infer())
        assert isinstance(inferred, nodes.ClassDef)
        assert len(inferred.bases) == 1
        assert inferred.bases[0].name == "int"

    @pytest.mark.parametrize(
        "second_arg",
        [
            "'foo'",  # str
            "None",
            "3.5",  # float
            "b'x'",  # bytes
        ],
    )
    def test_infer_typing_alias_non_int_second_argument(self, second_arg: str) -> None:
        """A non-int second argument must not crash the subscriptability check."""
        node = builder.extract_node(f"""
            from typing import _alias
            x = _alias(int, {second_arg})
            """)
        assert isinstance(node, nodes.Assign)
        assert isinstance(node.value, nodes.Call)
        # Should not raise TypeError from comparing the value with 0.
        inferred = next(node.value.infer())
        assert isinstance(inferred, nodes.ClassDef)

    @pytest.mark.parametrize(
        "second_arg, subscriptable",
        [
            ("1", True),  # positive int -> subscriptable
            ("-1", False),  # non-positive int -> not subscriptable
        ],
    )
    def test_infer_typing_alias_int_second_argument(
        self, second_arg: str, subscriptable: bool
    ) -> None:
        """A constant int count still drives the subscriptability check."""
        node = builder.extract_node(f"""
            from typing import _alias
            x = _alias(int, {second_arg})
            """)
        inferred = next(node.value.infer())
        assert isinstance(inferred, nodes.ClassDef)
        assert ("__class_getitem__" in inferred.locals) == subscriptable

    @pytest.mark.parametrize(
        "alias_args",
        [
            "",  # two missing arguments
            "int",  # one missing argument
            "int, float, tuple",  # one additional argument
        ],
    )
    def test_infer_typing_alias_incorrect_number_of_arguments(
        self, alias_args: str
    ) -> None:
        """
        Regression test for: https://github.com/pylint-dev/astroid/issues/2513

        Test that _alias() calls with the incorrect number of arguments can be inferred.
        """
        node = builder.extract_node(f"""
            from typing import _alias
            x = _alias({alias_args})
            """)
        assert isinstance(node, nodes.Assign)
        assert isinstance(node.value, nodes.Call)
        inferred = next(node.value.infer())
        assert isinstance(inferred, bases.Instance)
        assert inferred.name == "_SpecialGenericAlias"


class TestSpecialAlias:
    @pytest.mark.parametrize(
        "code",
        [
            "_CallableType()",
            "_TupleType()",
        ],
    )
    def test_special_alias_no_crash_on_empty_args(self, code: str) -> None:
        """
        Regression test for: https://github.com/pylint-dev/astroid/issues/2772

        Test that _CallableType() and _TupleType() calls with no arguments
        do not cause an IndexError.
        """
        # Should not raise IndexError
        module = builder.parse(code)
        assert isinstance(module, nodes.Module)
