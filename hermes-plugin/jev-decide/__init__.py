"""jev-decide plugin — registration.

One tool, `jev_decide`: hand a candidate list you built to the jev-browser-pilot decision policy
and get exactly one typed answer back. The tool is hidden from the model unless the `jev-pilot`
CLI can be resolved, so a machine without the library installed sees no dead tool.

Install: copy this directory to `$HERMES_HOME/plugins/jev-decide/`, then `hermes plugins enable
jev-decide`. The directory is the installable unit; nothing here imports Hermes internals.
"""

from __future__ import annotations

import logging

from . import schemas, tools

logger = logging.getLogger(__name__)

TOOLSET = "jev_decide"

TOOLS = {
    "jev_decide": (schemas.JEV_DECIDE, tools.jev_decide),
}


def register(ctx) -> None:
    """Wire the tool into Hermes. `ctx` is Hermes's PluginContext."""
    for name, (schema, handler) in TOOLS.items():

        def _handler(args, _handler=handler, **kwargs):
            return _handler(args, **kwargs)

        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema,
            handler=_handler,
            check_fn=tools.available,
        )
    logger.debug("jev-decide: registered %d tool(s)", len(TOOLS))
