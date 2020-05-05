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
    def get_from_path(self, path):
        """
        Return a sub-node from a path of nested tags
        """
        if path is None or len(path) == 0:
            return self

        tag = path[0]
        for item in self:
            if isinstance(item, NestedTags):
                if item.open_tag.rstrip() == tag:
                    return item.get_from_path(path[1:])

        raise KeyError("Invalid tag path")


    def add_or_update_directive(self, path, directive_name, directive_arguments):
        """
        Add/override a directive in the apache config file.
        path must be a list of tags, e.g. ["<VirtualHost *:80>", "<Directory /var/www>"],
            or an empty list/None in case you want to change something at the root of your file
        Returns whether something was changed
        Throws in case the path is invalid
        """
        node = self.get_from_path(path)

        for item in node:
            if not isinstance(item, Directive):
                continue
            else:
                if item.name == directive_name:
                    # We have found our item, let's update it
                    if item.args == directive_arguments:
                        return False # Nothing was changed
                    item.args = directive_arguments
                    return True

        # The item is not present at the given path. Let's add it
        node.append(Directive(directive_name, directive_arguments))
        return True

    def add_nested_tags(self, path, open_tag, close_tag):
        """
        Add a nested tag into the config
        Returns true on success, false in case a tag already existed at this path
        Throws in case of an invalid path
        """
        node = self.get_from_path(path)
        for item in node:
            if not isinstance(item, NestedTags):
                continue
            else:
                if item.open_tag == open_tag:
                    return False
        # The item is not present at the given path. Let's add it
        node.append(NestedTags(open_tag, close_tag))
        return True

    def remove_node(self, path, directive_name=None, nested_tag_open_tag=None):
        """
        This method removes a node under path.
        Pass a directive_name in case you want to remove a directive
        Pass nested_tag_open_tag in case you want to remove a nested tag
        Returns true on success
        Throws in case no such node is found
        """
        if(directive_name is None and nested_tag_open_tag is None):
            raise KeyError("No argument was passed")
        if(not directive_name is None and not nested_tag_open_tag is None):
            raise KeyError("Pass only one argument")

        parent = self.get_from_path(path)
        for item in parent:
            if directive_name is not None:
                if isinstance(item, Directive):
                    if item.name == directive_name:
                        parent.remove(item)
                        return True

            if nested_tag_open_tag is not None:
                if isinstance(item, NestedTags):
                    if item.open_tag == nested_tag_open_tag:
                        parent.remove(item)
                        return True

        raise KeyError("No such node")


    def get_apache_config(self, indentation=0):
        """
        This method returns the apache config contents as a string
        given the nested list returned by parse_config
        """
        config_string = ""

        if isinstance(self, Directive):
            config_string += (
                "\t"*indentation + self.name + " "
                + self.args + "\n"
            )
        if isinstance(self, Comment):
            config_string += (
                "\t"*indentation + "#" + self.comment_string
                + "\n"
            )
        if isinstance(self, BlankLine):
            config_string += "\n"

        if isinstance(self, NestedTags):
            config_string += "\t" * indentation + self.open_tag + "\n"

        for item in self:
            new_indent = indentation if isinstance(self, RootNode) else indentation+1
            config_string += item.get_apache_config(new_indent)

        if isinstance(self, NestedTags):
            config_string += "\t" * indentation + self.close_tag + "\n"

        return config_string


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
