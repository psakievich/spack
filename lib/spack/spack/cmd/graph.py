# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import argparse

import spack.cmd
import spack.config
import spack.store
from spack.active_environment import active_environment
from spack.cmd.common import arguments
from spack.concretize_ui import HeadlessUI, TerminalUI
from spack.graph import (
    DAGWithDependencyTypes,
    SimpleDAG,
    graph_ascii,
    graph_dot,
    select_with_context,
    static_graph_dot,
)
from spack.util import tty

description = "generate graphs of package dependency relationships"
section = "query"
level = "long"


def _context_level(value: str) -> int:
    """Validate the argument of the -A, -B and -C options"""
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not an integer")
    if result < 0:
        raise argparse.ArgumentTypeError(f"{value} is negative")
    return result


def _universe(args, env, specs):
    """Return the roots of the DAGs the context around the matched specs is taken from.

    Dependents only exist relative to a set of specs to look them up in, which is the whole
    DB with --installed, the whole environment if one is active, and the DAGs of the matched
    specs otherwise.
    """
    if args.installed:
        return spack.store.STORE.db.query()
    if env:
        return env.concrete_roots()
    return specs


def setup_parser(subparser: argparse.ArgumentParser) -> None:
    setattr(setup_parser, "parser", subparser)
    subparser.epilog = """
Outside of an environment, the command concretizes specs and graphs them, unless the
--installed option is given. In that case specs are matched from the current DB.

If an environment is active, specs are matched from the currently available concrete specs
in the lockfile.

The -A, -B and -C options work like the context options of ``grep``: the matched specs are
the "hits", and the graph is pruned to them plus the requested number of levels of context
around them. -A follows dependencies, like the lines ``grep`` prints after a hit, and -B
follows dependents, like the lines it prints before one. A level of 0 means "follow that
direction all the way to the terminal nodes", so the default output is the same as -A 0.

Dependents are only followed within the specs the command queries, i.e. the whole DB with
--installed, the whole lockfile within an environment, and the DAGs of the concretized specs
otherwise.

"""
    method = subparser.add_mutually_exclusive_group()
    method.add_argument(
        "-a", "--ascii", action="store_true", help="draw graph as ascii to stdout (default)"
    )
    method.add_argument(
        "-d", "--dot", action="store_true", help="generate graph in dot format and print to stdout"
    )

    subparser.add_argument(
        "-s",
        "--static",
        action="store_true",
        help="graph static (possible) deps, don't concretize (implies ``--dot``)",
    )
    subparser.add_argument(
        "-c",
        "--color",
        action="store_true",
        help="use different colors for different dependency types",
    )

    subparser.add_argument(
        "-i", "--installed", action="store_true", help="graph specs from the DB"
    )

    context = subparser.add_argument_group("context around the matched specs")
    context.add_argument(
        "-A",
        "--after-context",
        metavar="NUM",
        type=_context_level,
        default=None,
        help="graph NUM levels of dependencies below each matched spec (0 for all of them)",
    )
    context.add_argument(
        "-B",
        "--before-context",
        metavar="NUM",
        type=_context_level,
        default=None,
        help="graph NUM levels of dependents above each matched spec (0 for all of them)",
    )
    context.add_argument(
        "-C",
        "--context",
        metavar="NUM",
        type=_context_level,
        default=None,
        help="shorthand for ``-A NUM -B NUM``",
    )

    arguments.add_common_arguments(subparser, ["deptype", "long", "very_long", "specs"])


def graph(parser, args):
    env = active_environment()
    if args.installed and env:
        args.subparser.error("cannot use --installed with an active environment")

    if args.color and not args.dot:
        args.subparser.error("the --color option can be used only with --dot")

    dependency_levels, dependent_levels = args.after_context, args.before_context
    if args.context is not None:
        if dependency_levels is not None or dependent_levels is not None:
            args.subparser.error(
                "the -C option cannot be used together with -A or -B, it is a shorthand for both"
            )
        dependency_levels = dependent_levels = args.context

    use_context = dependency_levels is not None or dependent_levels is not None
    if use_context and args.static:
        args.subparser.error("the -A, -B and -C options cannot be used with --static")

    if args.installed:
        if not args.specs:
            specs = spack.store.STORE.db.query()
        else:
            result = []
            for item in args.specs:
                result.extend(spack.store.STORE.db.query(item))
            specs = list(set(result))
    elif env:
        specs = env.concrete_roots()
        if args.specs:
            specs = env.all_matching_specs(*args.specs)

    else:
        # Machine-readable output goes to stdout, so concretization must not print anything there
        ui = HeadlessUI() if args.dot else TerminalUI()
        specs = spack.cmd.parse_specs(args.specs, concretize=not args.static, ui=ui)

    if not specs:
        tty.die("no spec matching the query")

    if args.static:
        static_graph_dot(specs, depflag=args.deptype)
        return

    selection = None
    if use_context:
        specs, selection = select_with_context(
            specs,
            _universe(args, env, specs),
            dependency_levels=dependency_levels,
            dependent_levels=dependent_levels,
            depflag=args.deptype,
        )
        if not specs:
            tty.die("no spec matching the query")

    if args.dot:
        if args.very_long:
            node_label_fmt = "{name}{@version}{/hash}"
        elif args.long:
            node_label_fmt = "{name}{@version}{/hash:7}"
        else:
            node_label_fmt = "{name}{@version}"
        if args.color:
            builder = DAGWithDependencyTypes(node_label_fmt)
        else:
            builder = SimpleDAG(node_label_fmt)
        graph_dot(specs, builder=builder, depflag=args.deptype, selection=selection)
        return

    # ascii is default: user doesn't need to provide it explicitly
    debug = spack.config.CONFIG.get("config:debug")
    graph_ascii(specs[0], debug=debug, depflag=args.deptype, selection=selection)
    for spec in specs[1:]:
        print()  # extra line bt/w independent graphs
        graph_ascii(spec, debug=debug, depflag=args.deptype, selection=selection)
