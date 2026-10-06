# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import io

import spack.concretize
import spack.graph


def test_dynamic_dot_graph_mpileaks(config, mock_packages):
    """Test dynamically graphing the mpileaks package."""
    s = spack.concretize.concretize_one("mpileaks")
    stream = io.StringIO()
    spack.graph.graph_dot([s], out=stream)
    dot = stream.getvalue()

    nodes_to_check = ["mpileaks", "mpi", "callpath", "dyninst", "libdwarf", "libelf"]
    hashes, builder = {}, spack.graph.SimpleDAG()
    for name in nodes_to_check:
        current = s[name]
        current_hash = current.dag_hash()
        hashes[name] = current_hash
        node_options = builder.node_entry(current)[1]
        assert node_options in dot

    dependencies_to_check = [
        ("dyninst", "libdwarf"),
        ("callpath", "dyninst"),
        ("mpileaks", "mpi"),
        ("libdwarf", "libelf"),
        ("callpath", "mpi"),
        ("mpileaks", "callpath"),
        ("dyninst", "libelf"),
    ]
    for parent, child in dependencies_to_check:
        assert '  "{0}" -> "{1}"\n'.format(hashes[parent], hashes[child]) in dot


def test_ascii_graph_mpileaks(config, mock_packages, monkeypatch):
    monkeypatch.setattr(spack.graph.AsciiGraph, "_node_label", lambda self, node: node.name)
    s = spack.concretize.concretize_one("mpileaks")

    stream = io.StringIO()
    graph = spack.graph.AsciiGraph()
    graph.write(s, out=stream, color=False)
    graph_str = stream.getvalue()
    graph_str = "\n".join([line.rstrip() for line in graph_str.split("\n")])

    assert (
        graph_str
        == r"""o mpileaks
|\
| |\
| | |\
| | | |\
| | | | o callpath
| |_|_|/|
|/| |_|/|
| |/| |/|
| | |/|/|
| | | | o dyninst
| | |_|/|
| |/| |/|
| | |/|/|
| | | | |\
o | | | | | mpich
|\| | | | |
|\ \ \ \ \ \
| |_|/ / / /
|/| | | | |
| |/ / / /
| | | | o libdwarf
| |_|_|/|
|/| |_|/|
| |/| |/|
| | |/|/
| | | o libelf
| |_|/|
|/| |/|
| |/|/
| o | compiler-wrapper
|  /
| o gcc-runtime
|/
o gcc
"""
        or graph_str
        == r"""o mpileaks
|\
| |\
| | |\
| | | o callpath
| |_|/|
|/| |/|
| |/|/|
| | | o dyninst
| | |/|
| |/|/|
| | | |\
o | | | | mpich
|\| | | |
| |/ / /
|/| | |
| | | o libdwarf
| |_|/|
|/| |/|
| |/|/
| | o libelf
| |/|
|/|/
| o gcc-runtime
|/
o gcc
"""
    )


def test_select_with_context(config, mock_packages):
    """Test selecting a subgraph of mpileaks around a node, with context in both directions"""
    s = spack.concretize.concretize_one("mpileaks")

    def hashes(*names):
        return {s[name].dag_hash() for name in names}

    # Without any level, only the matches themselves are selected
    roots, selection = spack.graph.select_with_context([s["libdwarf"]], [s])
    assert selection == hashes("libdwarf")
    assert [x.name for x in roots] == ["libdwarf"]

    # One level of dependents: dyninst is the only package depending on libdwarf, and since
    # callpath is not selected, dyninst is the root of the subgraph
    roots, selection = spack.graph.select_with_context([s["libdwarf"]], [s], dependent_levels=1)
    assert selection == hashes("libdwarf", "dyninst")
    assert [x.name for x in roots] == ["dyninst"]

    # One level in both directions
    roots, selection = spack.graph.select_with_context(
        [s["libdwarf"]], [s], dependent_levels=1, dependency_levels=1
    )
    assert selection == hashes(
        "libdwarf", "dyninst", "libelf", "gcc", "gcc-runtime", "compiler-wrapper"
    )
    assert [x.name for x in roots] == ["dyninst"]

    # Zero levels means "follow that direction all the way to the terminal nodes"
    roots, selection = spack.graph.select_with_context([s["libelf"]], [s], dependent_levels=0)
    assert selection == hashes("libelf", "libdwarf", "dyninst", "callpath", "mpileaks")
    assert [x.name for x in roots] == ["mpileaks"]

    # Matches that are not part of the universe of specs are ignored
    other = spack.concretize.concretize_one("dt-diamond")
    roots, selection = spack.graph.select_with_context([other], [s], dependency_levels=0)
    assert not selection and not roots
