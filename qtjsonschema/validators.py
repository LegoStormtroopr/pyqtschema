import re

from PyQt5 import QtGui
from jsonschema import FormatChecker, FormatError

from .errors import ValidationError


class FormatValidator:
    def __init__(self, format):
        self._format = format
        self._checker = FormatChecker()

    def __call__(self, text):
        try:
            self._checker.check(text, self._format)
        except FormatError:
            raise ValidationError("Value {!r} does not confirm to format {!r}".format(text, self._format))
        return True


class RegexValidator:
    def __init__(self, pattern):
        self._matcher = re.compile(pattern)

    def __call__(self, text):
        if self._matcher.match(text) is not None:
            raise ValidationError("Value {!r} does not conform to regex {!r}".format(text, self._matcher))


class LengthValidator:
    def __init__(self, minimum=None, maximum=None):
        self.minimum = minimum
        self.maximum = maximum

    def __call__(self, text):
        if self.minimum is not None:
            if len(text) < self.minimum:
                raise ValidationError("Length of string {!r} is less than permitted ({})".format(text, self.minimum))

        if self.maximum is not None:
            if len(text) > self.maximum:
                raise ValidationError("Length of string {!r} is greater than permitted ({})".format(text, self.maximum))


class ValidationFormatter:
    """Format widget according to validator state"""
    VALID_COLOUR = '#c4df9b'
    INVALID_COLOUR = '#f6989d'

    def __init__(self, widget, require_validator=True):
        self._validators = []
        self._widget = widget
        self._default_tooltip = widget.toolTip()
        self._require_validator = require_validator

    def add_validator(self, validator):
        self._validators.append(validator)

    def __call__(self, value):
        # Don't perform validation if no validators
        if not self._validators and self._require_validator:
            return

        color_string = self.VALID_COLOUR
        tooltip = self._default_tooltip

        for validator in self._validators:
            try:
                validator(value)
            except ValidationError as err:
                tooltip = err.message
                color_string = self.INVALID_COLOUR
                break

        palette = self._widget.palette()
        colour = QtGui.QColor()
        colour.setNamedColor(color_string)
        palette.setColor(self._widget.backgroundRole(), colour)

        self._widget.setPalette(palette)
        self._widget.setToolTip(tooltip)
