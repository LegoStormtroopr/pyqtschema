#!/usr/bin/env python
"""
pyqtschema - Python Qt JSON Schema Tool

Generate a dynamic Qt form representing a JSON Schema.
Filling the form will generate JSON.
"""

import collections
import json
from json import dumps
from pathlib import Path

import click
from PyQt5 import QtCore, QtWidgets
from jsonschema import Draft4Validator, FormatChecker

from .widgets import create_widget


class MainWindow(QtWidgets.QWidget):
    schema = None

    def __init__(self, parent=None, validation_interval=100):
        QtWidgets.QWidget.__init__(self, parent)

        self.setWindowTitle("PyQt JSON Schema Editor")

        self.menu = QtWidgets.QMenuBar(self)
        self.file_menu = self.menu.addMenu("&File")

        _action_open_json = QtWidgets.QAction("&Open File", self)
        _action_open_json.triggered.connect(self._handle_open_json)

        _action_open_schema = QtWidgets.QAction("Open &JSON Schema", self)
        _action_open_schema.triggered.connect(self._handle_open_schema)

        _action_save = QtWidgets.QAction("&Save", self)
        _action_save.triggered.connect(self._handle_save)

        _action_quit = QtWidgets.QAction("&Close", self)
        _action_quit.triggered.connect(self._handle_quit)

        self.file_menu.addAction(_action_open_json)
        self.file_menu.addAction(_action_open_schema)
        self.file_menu.addAction(_action_save)
        self.file_menu.addSeparator()
        self.file_menu.addAction(_action_quit)

        # Scrollable region for schema form
        self.content_region = QtWidgets.QScrollArea(self)
        self.schema_widget = None
        self.schema = None

        self._validation_label = QtWidgets.QLabel()
        self._format_checker = FormatChecker()

        self._validation_timer = QtCore.QTimer(self)
        self._validation_timer.setInterval(validation_interval)
        self._validation_timer.timeout.connect(self._do_validation)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.menu)
        vbox.addWidget(self._validation_label)
        vbox.addWidget(self.content_region)
        vbox.setContentsMargins(0, 0, 0, 0)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addLayout(vbox)

        self.setLayout(hbox)

    @property
    def format_checker(self) -> FormatChecker:
        return self._format_checker

    def load_schema(self, file_path):
        """
            Load a schema and create the root element.
        """
        schema_path = Path(file_path).absolute()
        with open(schema_path) as f:
            schema = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)

        Draft4Validator.check_schema(schema)

        schema_title = schema.get("title", "<root>")
        self.setWindowTitle("{} - PyQt JSON Schema".format(schema_title))
        self.schema_widget = create_widget(schema_title, schema, schema_path.as_uri())
        self.content_region.setWidget(self.schema_widget)
        self.content_region.setWidgetResizable(True)
        self.schema = schema

        self._validation_timer.start()

    def load_json(self, json_file):
        """
            Load a schema and create the root element.
        """
        with open(json_file) as f:
            data = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)
            # from jsonschema import validate
            # validate(data, self.schema)
            self.schema_widget.load_json_object(data)

    def _do_validation(self):
        label = self._validation_label

        validator = Draft4Validator(self.schema, format_checker=self._format_checker)

        errors = [err for err in validator.iter_errors(self.schema_widget.dump_json_object())]
        if errors:
            error = errors[0]
            error_string = ("{} errors" if len(errors) > 1 else "{} error").format(len(errors))
            label.setText("{}.\nFirst error in {}:\n{}".format(error_string, '#/' + '/'.join(error.schema_path),
                                                               error.message))
            label.setStyleSheet("QLabel { color: red; }")

        else:
            label.setText("Object validates")
            label.setStyleSheet("QLabel { color: green; }")

    def _handle_open_json(self):
        # Open JSON File
        json_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Schema', filter="JSON File (*.json)")
        if json_file:
            self.load_json(json_file)

    def _handle_open_schema(self):
        # Open JSON Schema
        schema, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Schema', filter="JSON Schema (*.schema *.json)")
        if schema:
            self.load_schema(schema)

    def _handle_save(self):
        # Save JSON output
        obj = self.content_region.widget().dump_json_object()
        outfile, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save JSON', filter="JSON (*.json)")
        if outfile:
            with open(outfile, 'w') as f:
                f.write(dumps(obj, sort_keys=True, indent=4))

    def _handle_quit(self):
        # TODO: Check if saved?
        self.close()


@click.command()
@click.option('--schema', default=None, help='Schema file to generate an editing window from.')
@click.option('--json', default=None, help='Schema file to generate an editing window from.')
def json_editor(schema, json):
    import sys

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    main_window.resize(1000, 800)

    if schema:
        main_window.load_schema(schema)
        if json:
            main_window.load_json(json)

    app.exec_()


if __name__ == "__main__":
    json_editor()
