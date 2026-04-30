"""Built-in scanners for the user corpus builder.

Each module in this package registers its Scanner subclass via the
@register_scanner decorator. The package __init__ in mcp_server.user_corpus
imports all of them eagerly so the registry is populated at import time.

To add your own scanner:

    # mcp_server/user_corpus/scanners/my_format.py
    from ..scanner import Scanner, register_scanner

    @register_scanner
    class MyScanner(Scanner):
        type_id = "my-format"
        ...

Then reference it in your manifest as `type: my-format`.
"""
