import datetime
import pytest

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    LogicalNode,
    LogicalNodeOperator,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
    UnaryNodeOperator,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter


@pytest.mark.parametrize(
    "cel, expected_property_path, operator, expected_constant_type, expected_constant_value",
    [
        (
            "labels['previous_test_name-1'].tag.newPath['123456']=='fake alert'",
            ["labels", "previous_test_name-1", "tag", "newPath", "123456"],
            ComparisonNodeOperator.EQ,
            str,
            "fake alert",
        ),
        (
            "object.property.path=='fake alert'",
            ["object", "property", "path"],
            ComparisonNodeOperator.EQ,
            str,
            "fake alert",
        ),
        (
            "fakeProp == 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            str,
            "fake alert",
        ),
        (
            "fakeProp == 'It\\'s value with escaped single-quote'",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            str,
            "It's value with escaped single-quote",
        ),
        (
            'fakeProp == "It\\"s value with escaped double-quote"',
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            str,
            'It"s value with escaped double-quote',
        ),
        ("fakeProp == true", ["fakeProp"], ComparisonNodeOperator.EQ, bool, True),
        (
            "fakeProp == 12349983",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            int,
            12349983,
        ),
        (
            "fakeProp == 1234.9983",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            float,
            1234.9983,
        ),
        (
            "fakeProp == 'MON'",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            str,
            "MON",
        ),  # check that day-of-week short names do not get converted to dates
        ("fakeProp == 'mon'", ["fakeProp"], ComparisonNodeOperator.EQ, str, "mon"),
        (
            "fakeProp == '2025-01-20'",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            datetime.datetime,
            datetime.datetime(2025, 1, 20),
        ),
        (
            "fakeProp == '2025-01-20T14:35:27.123456'",
            ["fakeProp"],
            ComparisonNodeOperator.EQ,
            datetime.datetime,
            datetime.datetime(2025, 1, 20, 14, 35, 27, 123456),
        ),
        (
            "fakeProp != 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.NE,
            str,
            "fake alert",
        ),
        (
            "fakeProp > 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.GT,
            str,
            "fake alert",
        ),
        (
            "fakeProp >= 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.GE,
            str,
            "fake alert",
        ),
        (
            "fakeProp < 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.LT,
            str,
            "fake alert",
        ),
        (
            "fakeProp <= 'fake alert'",
            ["fakeProp"],
            ComparisonNodeOperator.LE,
            str,
            "fake alert",
        ),
        (
            "fakeProp.contains('\\'±CPU±\\'')",
            ["fakeProp"],
            ComparisonNodeOperator.CONTAINS,
            str,
            "'±CPU±'",
        ),
        (
            "fakeProp.startsWith('\\'±CPU±\\'')",
            ["fakeProp"],
            ComparisonNodeOperator.STARTS_WITH,
            str,
            "'±CPU±'",
        ),
        (
            "fakeProp.endsWith('\\'±CPU±\\'')",
            ["fakeProp"],
            ComparisonNodeOperator.ENDS_WITH,
            str,
            "'±CPU±'",
        ),
    ],
)
def test_simple_comparison_node(
    cel,
    expected_property_path,
    operator,
    expected_constant_type,
    expected_constant_value,
):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, ComparisonNode)
    assert actual.operator == operator

    # Check that second operand is a ConstantNode
    assert isinstance(actual.second_operand, ConstantNode)
    assert isinstance(actual.second_operand.value, expected_constant_type)
    assert actual.second_operand.value == expected_constant_value

    # Check that first operand is a PropertyAccessNode
    assert isinstance(actual.first_operand, PropertyAccessNode)
    assert actual.first_operand.path == expected_property_path


@pytest.mark.parametrize("cel, args", [
    ("fakeProp in ['string', 12345, true]", ["string", 12345, True]),
])
def test_simple_comparison_node_in(cel, args):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, ComparisonNode)
    assert actual.operator == ComparisonNodeOperator.IN

    # Check that second operand is a list
    assert isinstance(actual.second_operand, list)

    # verify that each element in the list is a ConstantNode with the correct value and type
    for i, arg in enumerate(actual.second_operand):
        assert isinstance(arg, ConstantNode)
        assert type(arg.value) == type(args[i])
        assert arg.value == args[i]


@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!fakeProp", UnaryNodeOperator.NOT),
        ("-fakeProp", UnaryNodeOperator.NEG),
        ("has(fakeProp)", UnaryNodeOperator.HAS),
    ],
)
def test_simple_unary_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, UnaryNode)
    assert actual.operator == operator

    # Check that first operand is a PropertyAccessNode
    assert isinstance(actual.operand, PropertyAccessNode)
    assert actual.operand.path == ["fakeProp"]


@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!firstFakeProp && !secondFakeProp", LogicalNodeOperator.AND),
        ("!firstFakeProp || !secondFakeProp", LogicalNodeOperator.OR),
    ],
)
def test_simple_logical_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a LogicalNode
    assert isinstance(actual, LogicalNode)
    assert actual.operator == operator

    # Check that left is UnaryNode with NOT operator
    assert isinstance(actual.left, UnaryNode)
    assert actual.left.operator == UnaryNodeOperator.NOT

    # Check that left.operand is PropertyAccessNode
    assert isinstance(actual.left.operand, PropertyAccessNode)
    assert actual.left.operand.path == ["firstFakeProp"]

    # Check that right is UnaryNode with NOT operator
    assert isinstance(actual.right, UnaryNode)
    assert actual.right.operator == UnaryNodeOperator.NOT

    # Check that left.operand is PropertyAccessNode
    assert isinstance(actual.right.operand, PropertyAccessNode)
    assert actual.right.operand.path == ["secondFakeProp"]

@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!(fakeProp)", UnaryNodeOperator.NOT),
        ("-(fakeProp)", UnaryNodeOperator.NEG),
    ],
)
def test_parenthesis_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, UnaryNode)
    assert actual.operator == operator

    # Check that the operand is ParenthesesNode
    assert isinstance(actual.operand, ParenthesisNode)

    # Check that the operand.expression is PropertyAccessNode
    assert isinstance(actual.operand.expression, PropertyAccessNode)
    assert actual.operand.expression.path == ["fakeProp"]
