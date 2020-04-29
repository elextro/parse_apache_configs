from pyparsing import Word, oneOf, White, OneOrMore, alphanums, LineEnd, \
    Group, Suppress, Literal, printables, ParseException, ungroup

# For tags that have an argument in the form of
# a conditional expression. The reason this is done
# is so that a tag with the ">" operator in the
# arguments will parse correctly.
OPERAND = Word(alphanums + "." + '"' + '/-' + "*:^_|![]?$%@)(#=`'}{&+~" + '\\')
OPERATOR = oneOf(["<=", ">=", "==", "!=", "<", ">", "~"], useRegex=False)
EXPRESSION_TAG = Word(alphanums) + White() + OPERAND + White() + OPERATOR + White() + OPERAND

# LITERAL_TAG will match tags that do not have
# a conditional expression. So any other tag
# with arguments that don't contain OPERATORs
LITERAL_TAG = OneOrMore(Word(
    alphanums + '*:' + '/' + '"-' + '.' + " " + "^" + "_" + "!" + "[]?$"
    + "'" + '\\' + "*:^_|![]?$%@)(#=`'}{&+~"  
))
# Will match the start of any tag
TAG_START_GRAMMAR = Group(Literal("<") + (EXPRESSION_TAG | LITERAL_TAG)
                          + Literal(">") + LineEnd())

# Will match the end of any tag
TAG_END_GRAMMAR = Group(Literal("</") + Word(alphanums) + Literal(">")
                        + LineEnd())

# Will match any directive. We are performing
# a simple parse by matching the directive on
# the left, and everything else on the right.
ANY_DIRECTIVE = Group(Word(alphanums+'_-@.') + Suppress(White())
                      + Word(printables + "     ") + LineEnd())

COMMENT = Group(
    (Literal("#") + LineEnd()) ^
    (Literal("#")
     + OneOrMore(Word(alphanums + '~*:/"-.^\_![]?$%><' + "',|`)(#;}{=@+"))
     + LineEnd())
)

BLANK_LINE = Group(LineEnd())

# A line. Will match every grammar defined above.
LINE = (TAG_END_GRAMMAR ^ TAG_START_GRAMMAR ^ ANY_DIRECTIVE
        ^ COMMENT ^ BLANK_LINE)

CONFIG_FILE = OneOrMore(LINE)


class Node(list):
    pass

class Directive(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args


class Comment(Node):
    def __init__(self, comment_string):
        self.comment_string = comment_string


class BlankLine(Node):
    pass


class NestedTags(Node):
    def __init__(self, open_tag, close_tag):
        self.open_tag = open_tag
        self.close_tag = close_tag


class RootNode(Node):
    pass


class ParseApacheConfig:

    def __init__(self, apache_config_path='', apache_file_as_string=''):
        """Initialize the ParseApacheConfig object

        Only one of the two parameters may be given at one time.
        apache_config_path is the absolute path to the apache config file
        to be parsed. apache_file_as_string is the file to be parsed, as a
        string.

        :param apache_config_path: ``string``
        :param apache_file_as_string: ``string``
        """
        if apache_config_path and apache_file_as_string:
            raise Exception(
                "ERROR - Cannot pass an apache config path and the apache "
                "file as a string."
            )

        elif not apache_config_path and not apache_file_as_string:
            raise Exception(
                "ERROR - Either an apache config file path or the string "
                "representation of the file must be passed!"
            )

        self.apache_config_path = apache_config_path
        self.apache_file_as_string = apache_file_as_string

    def parse_config(self):
        """Parse the apache config file and return a list representation.
        """

        # This is just a list of the config file lines tokenized
        conf_list = self._return_conf_list()
        config_stack = []
        root = RootNode()
        config_stack.append(root)
        for tokenized_line in conf_list:
            if self._is_directive(tokenized_line):
                config_stack[-1].append(
                    Directive(tokenized_line[0], tokenized_line[1])
                )
            elif self._is_comment(tokenized_line):
                config_stack[-1].append(
                    Comment(" ".join(tokenized_line[1:-1]))
                )
            elif self._is_blank_line(tokenized_line):
                config_stack[-1].append(BlankLine())
            elif self._is_open_tag(tokenized_line):
                close_tag = self._get_corresponding_close_tag(tokenized_line)
                # Take everything from tokenized_line minus the last
                # character (new line).
                open_tag = "".join(tokenized_line[0:-1])
                config_stack.append(NestedTags(open_tag, close_tag))
            elif self._is_close_tag(tokenized_line):
                block = config_stack.pop()
                config_stack[-1].append(block)

        return config_stack[-1]

    def get_apache_config(self, nested_list_conf):
        """
        This method returns the apache config contents as a string
        given the nested list returned by parse_config
        """
        stack = []
        stack.append(nested_list_conf)
        depth = -1
        config_string = ""
        while(len(stack) > 0):
            current = stack[-1]
            if isinstance(current, Directive):
                config_string += (
                    "\t"*depth + current.name + " "
                    + current.args + "\n"
                )
                stack.pop()
                continue
            if isinstance(current, Comment):
                config_string += (
                    "\t"*depth + "#" + current.comment_string
                    + "\n"
                )
                stack.pop()
                continue
            if isinstance(current, BlankLine):
                config_string += "\n"
                stack.pop()
                continue

            if hasattr(current, 'should_close'):
                depth -= 1
                if isinstance(current, NestedTags):
                    config_string += "\t" * depth + current.close_tag + "\n"
                stack.pop()
                continue

            if isinstance(current, NestedTags):
                config_string += "\t" * depth + current.open_tag + "\n"

            current.should_close = True
            depth += 1
            stack.extend(reversed(current))

        return config_string

    def add_directive(self, nested_list_conf, directive_name,
                      directive_arguments, *path):
        """
        This method adds/overrides a directivie in the apache config file.
        """

        # Variables
        if len(path) == 0:
            tag_path = []
        else:
            tag_path = []
            for string in path:
                tag_path.append(string)

        stack = []
        stack.append(nested_list_conf)
        # A dummy nested list so we don't modify the orignal
        # as we are iterating through the list
        dummy_nested_list_conf = list(nested_list_conf)

        # Iterating through the list
        while(len(tag_path) > 0):

            # If we iterate through the entire list and tag_path is still
            # greater than zero, then the tag is not there.
            if len(dummy_nested_list_conf) == 0:
                raise Exception("Y U GIVE INCORRECT PATH!?")

            # Pop the first element off the stack
            current = dummy_nested_list_conf.pop(0)
            if isinstance(current, NestedTags):
                if current.open_tag.rstrip() == tag_path[0]:
                    # We are only conerned with the current block of the config
                    dummy_nested_list_conf = current
                    stack.append(current)
                    tag_path.pop(0)

        directive = Directive(directive_name, directive_arguments)
        # Checking to see if directive is already there.
        # If it is, override it.
        for directive_object in stack[-1]:
            if not isinstance(directive_object, Directive):
                continue
            else:
                if directive_object.name == directive_name:
                    directive_object.args = directive_arguments
                    return nested_list_conf
        # If we have reached this point, the directive is not in the
        # config file and we can add it.
        stack[-1].append(directive)

        return nested_list_conf

    def _is_open_tag(self, tokenized_line):
        """
        Returns true if tozenized_line is an apache start tag.
        """
        if tokenized_line[0] == '<':
            return True
        else:
            return False

    def _is_directive(self, tokenized_line):
        """
        Return true if tokenized_line is an apache directive.
        """
        string_line = " ".join(tokenized_line)
        try:
            ANY_DIRECTIVE.parseString(string_line)
        except ParseException:
            return False
        return True

    def _is_comment(self, tokenized_line):
        """
        Return true is tokenized_line is an apache comment
        """
        if tokenized_line[0] == "#":
            return True
        else:
            return False

    def _is_close_tag(self, tokenized_line):
        """
        Returns true if tokenized_line is an apache end tag.
        """
        if tokenized_line[0] == '</':
            return True
        else:
            return False

    def _is_blank_line(self, tokenized_line):
        """
        Return true if tokenized_line is a blank line.
        """
        if tokenized_line[0] == '\n':
            return True
        else:
            return False

    def _get_corresponding_close_tag(self, tokenized_line):
        """
        Return the close tag of tokenized_line
        """
        if self._is_open_tag(tokenized_line):
            opentag_list = tokenized_line[1].split(" ")
            close_tag = "</" + opentag_list[0] + ">"
            return close_tag
        else:
            raise Exception("Y U TRY TO CALL METHOD WITH NO OPEN TAG?!?!")

    def _return_conf_list(self):
        """
        Iterates through the apache config file, building a list whoes entries
        are a tokenized version of each line in the config file.

        :returns: ``list``
        """
        # Variables
        conf_list = []

        # A file path was given
        if self.apache_config_path:
            with open(self.apache_config_path, "r") as apache_config:
                for line in apache_config:
                    parsed_result_line = ungroup(LINE).parseString(line)
                    conf_list.append(parsed_result_line)
        # The file was given as a string
        # TODO: Write tests for a file given as a string!
        elif self.apache_file_as_string:
            conf_file_line_list = self.apache_file_as_string.split("\n")
            for line in conf_file_line_list:
                # Add the delimiter back in
                line = line + "\n"
                parsed_result_line = ungroup(LINE).parseString(line)
                conf_list.append(parsed_result_line)
        return conf_list
