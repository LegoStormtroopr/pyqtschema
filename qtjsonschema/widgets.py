"""
Widget definitions for JSON schema elements.
"""

from PyQt5 import QtCore, QtWidgets, QtGui

from .errors import UnsupportedSchemaError
from .tools import FileResourceLoader, HTTPResourceLoader, Context, DocumentLoader, create_cached_uri_loader_registry
from .validators import ValidationFormatter, FormatValidator, LengthValidator, RegexValidator


# Widgets supporting $ref
# $ref, items, allOf, anyOf, additionalItems, dependencies,
# oneOf, type, extends, properties, patternProperties,
# additionalProperties


def iter_layout_widgets(layout):
    for i in range(layout.count()):
        yield layout.itemAt(i).widget()


def iter_widgets(object):
    for i in range(object.count()):
        yield object.widget(i)


def not_implemented_property():
    """Property descriptor which raises NotImplementedError on __get__"""

    def getter(self):
        raise NotImplementedError

    return property(getter)


class QColorButton(QtWidgets.QPushButton):
    """Color picker widget QPushButton subclass.

    Implementation derived from https://martinfitzpatrick.name/article/qcolorbutton-a-color-selector-tool-for-pyqt/
    """

    colorChanged = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(QColorButton, self).__init__(*args, **kwargs)

        self._color = None
        self.pressed.connect(self.onColorPicker)

    def color(self):
        return self._color

    def setColor(self, color):
        if color != self._color:
            self._color = color
            self.colorChanged.emit()

        if self._color:
            self.setStyleSheet("background-color: %s;" % self._color)
        else:
            self.setStyleSheet("")

    def onColorPicker(self):
        dlg = QtWidgets.QColorDialog(self)
        if self._color:
            dlg.setCurrentColor(QtGui.QColor(self._color))

        if dlg.exec_():
            self.setColor(dlg.currentColor().name())

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.setColor(None)

        return super(QColorButton, self).mousePressEvent(event)


class JSONBaseWidget:
    """Base class for JSON handling widgets"""

    def __init__(self, name: str, schema: dict, ctx: Context, parent: 'JSONBaseWidget'):
        super().__init__()

        self.name = name
        self.schema = schema
        self.parent = parent
        self.ctx = ctx

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        raise NotImplementedError

    def dump_json_object(self):
        raise NotImplementedError

    def initialise(self):
        if 'default' in self.schema:
            self.load_json_object(self.schema['default'])

    def load_json_object(self, data):
        raise NotImplementedError


class UnsupportedSchemaWidget(JSONBaseWidget, QtWidgets.QLabel):
    """Widget representation of an unsupported schema element.

    Presents a label noting the name of the element and its type.
    If the element is a reference, the reference name is listed instead of a type.
    """

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        QtWidgets.QLabel.__init__(self, "(Unsupported schema entry: {}, {})"
                                  .format(name, schema.get("type", "(?)")), parent)
        self.setStyleSheet("QLabel { font-style: italic; }")

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        return True

    def dump_json_object(self):
        return "(unsupported)"

    def load_json_object(self, value):
        pass


class JSONObjectWidget(JSONBaseWidget, QtWidgets.QGroupBox):
    """Widget representation of an object.

    Objects have properties, each of which is a widget of its own.
    We display these in a group-box, which on most platforms will include a border.
    """

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        self.setTitle(self.name)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self.layout)
        self.setFlat(False)

        if "description" in schema:
            self.setToolTip(schema['description'])

        self.properties = {}

        if "properties" not in schema:
            label = QtWidgets.QLabel("Invalid object description (missing properties)", self)
            label.setStyleSheet("QLabel { color: red; }")
            self.layout.addWidget(label)

        else:
            for k, v in schema['properties'].items():
                widget = _create_widget(k, v, ctx, self)
                self.layout.addWidget(widget)
                self.properties[k] = widget

                # TODO pattern properties control widget

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        return schema.get("type") == "object"

    def dump_json_object(self) -> dict:
        return {k: v.dump_json_object() for k, v in self.properties.items()}

    def load_json_object(self, data: dict):
        for k, v in data.items():
            try:
                widget = self.properties[k]
            except KeyError:
                continue  # Probably a patternProperty

            widget.load_json_object(v)


class JSONPrimitiveBaseWidget(JSONBaseWidget, QtWidgets.QWidget):
    """Base class for JSON serialising widgets which have a single input widget"""

    PRIMITIVE_CLASS = not_implemented_property()

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)
        layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(schema.get('title', name))
        if "description" in schema:
            self.label.setToolTip(schema['description'])

        self._primitive_widget = self._create_primitive_widget()

        layout.addWidget(self.label)
        layout.addWidget(self._primitive_widget)

        self.setLayout(layout)

    def _create_primitive_widget(self):
        return self.PRIMITIVE_CLASS(self)

class JSONEnumWidget(JSONPrimitiveBaseWidget):
    """Widget representation of an enumerated property."""

    PRIMITIVE_CLASS = QtWidgets.QComboBox

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        self._enum_values = schema['enum']
        self._primitive_widget.addItems([str(e) for e in schema['enum']])

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        return "enum" in schema

    def dump_json_object(self):
        index = self._primitive_widget.currentIndex()
        return self._enum_values[index]

    def load_json_object(self, obj):
        index = self._enum_values.index(obj)
        self._primitive_widget.setCurrentIndex(index)


class JSONColorStringWidget(JSONPrimitiveBaseWidget):
    """Widget representation of a string with the 'color' format keyword."""

    PRIMITIVE_CLASS = QColorButton

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        return (schema.get('type') == 'string' and
                schema.get('format') == 'color')

    def dump_json_object(self) -> str:
        return self._primitive_widget.color()

    def load_json_object(self, data: str):
        self._primitive_widget.setColor(data)


class JSONDateTimeStringWidget(JSONPrimitiveBaseWidget):
    """Widget representation of a string with the 'date-time' format keyword."""
    def _create_primitive_widget(self):
        widget = QtWidgets.QDateTimeEdit()
        widget.setCalendarPopup(True)
        return widget

    @classmethod
    def supports_schema(cls, schema: dict) -> bool:
        return (schema.get('type') == 'string' and
                schema.get('format') == 'date-time')

    def dump_json_object(self) -> str:
        date_time = self._primitive_widget.dateTime()
        return date_time.toString("yyyy-MM-ddThh:mm:ssZ")

    def load_json_object(self, data: str):
        date_time = QtCore.QDateTime.fromString(data, "yyyy-MM-ddThh:mm:ssZ")
        self._primitive_widget.setDateTime(date_time)



class JSONStringWidget(JSONPrimitiveBaseWidget):
    """Widget representation of a string.

    Strings are text boxes with labels for names.
    """

    PRIMITIVE_CLASS = QtWidgets.QLineEdit

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        self._validator = ValidationFormatter(self._primitive_widget)

        if 'pattern' in schema:
            pattern = schema["pattern"]
            self._validator.add_validator(RegexValidator(pattern))

        if 'format' in schema:
            format = schema["format"]
            self._validator.add_validator(FormatValidator(format))

            if format == 'uri':
                dialogue_button = QtWidgets.QPushButton()
                icon = dialogue_button.style().standardIcon(QtWidgets.QStyle.SP_FileLinkIcon)
                dialogue_button.setIcon(icon)
                dialogue_button.clicked.connect(self._load_uri_from_file)
                self.layout().addWidget(dialogue_button)

        if 'minLength' in schema:
            min_length = schema["minLength"]
            self._validator.add_validator(LengthValidator(minimum=min_length))

        max_length = schema.get("maxLength")
        if max_length is not None:
            self._primitive_widget.setMaxLength(max_length)

        self._primitive_widget.textChanged.connect(self._validate_text)

    @classmethod
    def supports_schema(cls, schema):
        return schema.get('type') == 'string'

    def dump_json_object(self):
        return str(self._primitive_widget.text())

    def load_json_object(self, data):
        self._primitive_widget.setText(data)

    def _load_uri_from_file(self):
        url, filter = QtWidgets.QFileDialog.getOpenFileUrl(self, 'Open URL')
        if url.isEmpty():
            return

        self._primitive_widget.setText(url.toString())

    def _validate_text(self):
        self._validator(self._primitive_widget.text())


class SpinBoxWidgetBase(JSONPrimitiveBaseWidget):
    """Base class for spinbox JSON serialising widgets."""

    PRIMITIVE_CLASS = not_implemented_property()
    step = not_implemented_property()

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def dump_json_object(self):
        return self._primitive_widget.value()

    def load_json_object(self, data):
        self._primitive_widget.setValue(data)

    def _set_limits(self, schema: dict):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += self.step

            self._primitive_widget.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= self.step

            self._primitive_widget.setMaximum(maximum)


class JSONIntegerWidget(SpinBoxWidgetBase):
    """Widget representation of an integer (SpinBox)."""

    PRIMITIVE_CLASS = QtWidgets.QSpinBox
    step = 1

    @classmethod
    def supports_schema(cls, schema):
        return schema.get('type') == 'integer'


class JSONNumberWidget(SpinBoxWidgetBase):
    """Widget representation of a number (DoubleSpinBox)."""

    PRIMITIVE_CLASS = QtWidgets.QDoubleSpinBox
    step = 0.01

    @classmethod
    def supports_schema(cls, schema):
        return schema.get('type') == 'number'


class JSONBooleanWidget(JSONPrimitiveBaseWidget):
    """Widget representing a boolean (CheckBox)."""

    PRIMITIVE_CLASS = QtWidgets.QCheckBox

    @classmethod
    def supports_schema(cls, schema):
        return schema.get('type') == 'boolean'

    def dump_json_object(self):
        return self._primitive_widget.isChecked()

    def load_json_object(self, data):
        self._primitive_widget.setChecked(data)


class JSONArrayWidget(JSONBaseWidget, QtWidgets.QWidget):
    """Widget representation of an array.

    Arrays can contain multiple objects of a type, or they can contain objects of specific types.
    We include a label and button for adding types. """

    def __init__(self, name: str, schema: dict, ctx: Context, parent: JSONBaseWidget):
        super().__init__(name, schema, ctx, parent)

        self.layout = QtWidgets.QVBoxLayout()
        self.controls_layout = QtWidgets.QHBoxLayout()
        self.items_layout = QtWidgets.QVBoxLayout()

        label = QtWidgets.QLabel(name, self)
        label.setStyleSheet("QLabel { font-weight: bold; }")
        if "description" in schema:
            label.setToolTip(schema['description'])

        append_button = QtWidgets.QPushButton("", self)
        icon = append_button.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        append_button.setIcon(icon)
        append_button.clicked.connect(self.click_add)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                            QtWidgets.QSizePolicy.Maximum)
        append_button.setSizePolicy(size_policy)

        remove_button = QtWidgets.QPushButton("", self)
        icon = remove_button.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon)
        remove_button.setIcon(icon)
        remove_button.clicked.connect(self.click_remove)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                            QtWidgets.QSizePolicy.Maximum)
        remove_button.setSizePolicy(size_policy)

        self.controls_layout.addWidget(label)
        self.controls_layout.addWidget(append_button)
        self.controls_layout.addWidget(remove_button)

        self.layout.addLayout(self.controls_layout)

        self.items_list = QtWidgets.QListWidget(self)
        self.widget_stack = QtWidgets.QStackedWidget(self)

        self.items_list.currentItemChanged.connect(self._current_item_changed)

        self.layout.addWidget(self.items_list)
        self.layout.addWidget(self.widget_stack)

        self.setLayout(self.layout)

        try:
            self.items_schema = schema['items']
        except KeyError:
            raise UnsupportedSchemaError("Arrays require items")

        self.additional_item_schema = schema.get("additionalItems")

    @classmethod
    def supports_schema(cls, schema):
        return schema.get('type') == 'array'

    def add_item(self, data=None):
        index = self.items_list.count()
        schema = self._get_item_schema(index)
        obj = _create_widget("Item #{:d}".format(index), schema, self.ctx, self)

        self.items_list.addItem("# {}".format(index))
        self.widget_stack.addWidget(obj)

        if data is not None:
            obj.load_json_object(data)

    def click_add(self):
        self.add_item()

    def click_remove(self):
        self.remove_item()

    def dump_json_object(self):
        return [w.dump_json_object() for w in iter_widgets(self.widget_stack)]

    def load_json_object(self, data):
        for i, datum in enumerate(data):
            if i < self.widget_stack.count():
                self.widget_stack.widget(i).load_json_object(datum)
            else:
                self.add_item(datum)

    def remove_item(self):
        last_item_index = self.items_list.count() - 1
        if last_item_index < 0:
            return

        self.items_list.takeItem(last_item_index)

        widget = self.widget_stack.widget(last_item_index)
        self.widget_stack.removeWidget(widget)

    def _current_item_changed(self, current, previous):
        index = self.items_list.indexFromItem(current).row()
        self.widget_stack.setCurrentIndex(index)

    def _get_item_schema(self, index):
        if isinstance(self.items_schema, list):
            try:
                schema = self.items_schema[index]
            except IndexError:
                schema = self.additional_item_schema
                assert schema is not None
        else:
            assert isinstance(self.items_schema, dict)
            schema = self.items_schema

        return schema


supported_widgets = (
    JSONObjectWidget,
    JSONEnumWidget,
    JSONIntegerWidget,
    JSONNumberWidget,
    JSONBooleanWidget,
    JSONArrayWidget,
    JSONDateTimeStringWidget,
    JSONColorStringWidget,
    JSONStringWidget,
)


def create_widget(name: str, schema: dict, schema_uri: str = None) -> JSONBaseWidget:
    """Create widget according to given JSON schema.
    if `schema_uri` is omitted, external references may only be resolved against absolute URI `id` fields--
    
    :param name: widget name
    :param schema: dict-like JSON object
    :param schema_uri: URI corresponding to given schema object
    """
    registry_class = create_cached_uri_loader_registry()
    registry = registry_class()

    http_loader = HTTPResourceLoader()
    file_resource_loader = FileResourceLoader()
    document_loader = DocumentLoader(schema, schema_uri)

    registry.register_for_scheme('http', http_loader)
    registry.register_for_scheme('https', http_loader)
    registry.register_for_scheme('file', file_resource_loader)
    registry.register_for_scheme(None, document_loader)

    ctx = Context(schema_uri or "#", registry)
    return _create_widget(name, schema, ctx, None)


def _create_widget(name: str, schema: dict, ctx: Context, parent: JSONBaseWidget) -> JSONBaseWidget:
    if "id" in schema:
        ctx = ctx.follow_uri(schema['id'])

    while "$ref" in schema:
        schema = ctx.dereference(schema['$ref'])

    widget_class = next((c for c in supported_widgets if c.supports_schema(schema)),
                        UnsupportedSchemaWidget)

    # If instantiation fails, error
    try:
        widget = widget_class(name, schema, ctx, parent)
    except UnsupportedSchemaError:
        widget = UnsupportedSchemaWidget(name, schema, ctx, parent)

    widget.initialise()
    return widget
