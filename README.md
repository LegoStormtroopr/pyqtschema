# PyQtJSONSchema (qtjsonschema)

PyQtJSONSchema is a library which can read a JSON schema (Draft 4) and generate a corresponding PyQt editor widget.


A commandline tool is provided to generate a dynamic form from a JSON schema, and then generate JSON from that form:

    python -m qtjsonschema


# Supported keywords & types
All primitive types are supported, though as yet not all validation keywords are.
Currently unsupported validation keywords:
* `patternProperties`
* `additionalProperties`
* `oneOf`
* `anyOf`
* `allOf`
* `not`
* `dependencies`
* `maxItems`
* `minItems`
* `uniqueItems`

Of these keywords, the following are likely to be supported soon:
* `patternProperties`
* `additionalProperties`
* `dependencies`

In short, the combinators `anyOf`, `allOf`, `not`, and `oneOf` are a little more complicated with respect to a simple top-down tree generation, and will require more complicated handling.

Those validation keywords in the above todo-soon list will be implemented once custom property addition is supported

Requires PyQt5 and Python3
