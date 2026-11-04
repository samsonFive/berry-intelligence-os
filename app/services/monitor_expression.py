"""Small Boolean matcher for captured article bodies; never executes expressions."""
import re
from app.services.topic_retrieval import normalize


def parse(expression):
    tokens = re.findall(r'"[^"\n]+"|\(|\)|[^\s()"]+', expression)
    if ''.join(tokens) != re.sub(r'\s+', '', expression):
        # Spaces within quoted phrases are significant, so compare after removing them too.
        if re.sub(r'\s+', '', ''.join(tokens)) != re.sub(r'\s+', '', expression):
            raise ValueError('Check the quotes in this advanced expression.')
    position = 0

    def atom():
        nonlocal position
        if position >= len(tokens):
            raise ValueError('Incomplete advanced expression.')
        token = tokens[position]; position += 1
        if token == 'NOT':
            return ('not', atom())
        if token == '(':
            result = disjunction()
            if position >= len(tokens) or tokens[position] != ')':
                raise ValueError('Check the parentheses in this advanced expression.')
            position += 1
            return result
        if token in {'AND', 'OR', ')'}:
            raise ValueError('Check the operators in this advanced expression.')
        if ':' in token or '*' in token or '+' in token:
            raise ValueError('Historical backfill supports terms, phrases, AND, OR, NOT and parentheses. Remove provider-specific operators.')
        return ('not', ('term', token[1:])) if token.startswith('-') else ('term', token.strip('"'))

    def conjunction():
        nonlocal position
        result = atom()
        while position < len(tokens) and tokens[position] not in {'OR', ')'}:
            if tokens[position] == 'AND':
                position += 1
            result = ('and', result, atom())
        return result

    def disjunction():
        nonlocal position
        result = conjunction()
        while position < len(tokens) and tokens[position] == 'OR':
            position += 1
            result = ('or', result, conjunction())
        return result

    tree = disjunction()
    if position != len(tokens):
        raise ValueError('Check the parentheses in this advanced expression.')
    return tree


def matches(expression, body):
    text = ' ' + normalize(body) + ' '
    def evaluate(node):
        if node[0] == 'term':
            return (' ' + normalize(node[1]) + ' ') in text
        if node[0] == 'not':
            return not evaluate(node[1])
        if node[0] == 'and':
            return evaluate(node[1]) and evaluate(node[2])
        return evaluate(node[1]) or evaluate(node[2])
    return evaluate(parse(expression))


def grouped_expression(expression):
    """Avoid redundant nested groups that Google News silently returns empty."""
    def render(node, parent=None):
        operator = node[0]
        if operator == 'term':
            value = node[1]
            return '"' + value + '"' if ' ' in value else value
        if operator == 'not':
            return 'NOT ' + render(node[1], 'not')
        text = render(node[1], operator) + (' AND ' if operator == 'and' else ' OR ') + render(node[2], operator)
        return '(' + text + ')' if operator == 'or' and parent != 'or' or parent == 'not' else text
    return render(parse(expression), 'and')
