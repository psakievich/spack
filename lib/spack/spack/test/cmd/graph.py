# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import pytest

import spack.concretize
from spack.main import SpackCommand, SpackCommandError

graph = SpackCommand("graph")


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_ascii():
    """Tests spack graph --ascii"""
    graph("--ascii", "dt-diamond")


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_dot():
    """Tests spack graph --dot"""
    graph("--dot", "dt-diamond")


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_dot_hashes():
    """Tests that --long/--very-long control the hash in --dot node labels"""
    spec = spack.concretize.concretize_one("dt-diamond")
    no_hash = f'label="{spec.format("{name}{@version}")}"'
    short_hash = f'label="{spec.format("{name}{@version}{/hash:7}")}"'
    full_hash = f'label="{spec.format("{name}{@version}{/hash}")}"'

    none = graph("--dot", "dt-diamond")
    assert no_hash in none and short_hash not in none

    short = graph("--dot", "--long", "dt-diamond")
    assert short_hash in short and full_hash not in short

    full = graph("--dot", "--very-long", "dt-diamond")
    assert full_hash in full


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_static():
    """Tests spack graph --static"""
    graph("--static", "dt-diamond")


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_installed():
    """Tests spack graph --installed"""

    graph("--installed")

    with pytest.raises(SpackCommandError):
        graph("--installed", "dt-diamond")


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_deptype():
    """Tests spack graph --deptype"""
    graph("--deptype", "all", "dt-diamond")


def test_graph_no_specs(mock_packages):
    """Tests spack graph with no arguments"""

    with pytest.raises(SpackCommandError):
        graph()


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_after_context():
    """Tests that -A graphs only the given number of levels of dependencies"""
    out = graph("--dot", "-A", "1", "dt-diamond")

    assert 'label="dt-diamond@' in out
    assert 'label="dt-diamond-left@' in out
    assert 'label="dt-diamond-right@' in out
    # dt-diamond-bottom is two levels below dt-diamond
    assert "dt-diamond-bottom" not in out


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_after_context_zero_follows_all_levels():
    """Tests that -A 0 is the same as the default output, which graphs all dependencies"""
    default = graph("--dot", "dt-diamond")
    all_levels = graph("--dot", "-A", "0", "dt-diamond")

    assert sorted(default.splitlines()) == sorted(all_levels.splitlines())


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_before_context():
    """Tests that -B graphs only the given number of levels of dependents"""
    out = graph("--dot", "--installed", "-B", "1", "libelf")

    assert 'label="libelf@' in out
    # libdwarf and dyninst both depend directly on libelf
    assert 'label="libdwarf@' in out
    assert 'label="dyninst@' in out
    # callpath is two levels above libelf
    assert "callpath" not in out
    # dependencies are not followed unless -A or -C is given
    assert "compiler-wrapper" not in out


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_before_context_zero_follows_all_levels():
    """Tests that -B 0 follows dependents up to the roots of the DAG"""
    out = graph("--dot", "--installed", "-B", "0", "libelf")

    assert 'label="libelf@' in out
    assert 'label="dyninst@' in out
    assert 'label="callpath@' in out
    assert 'label="mpileaks@' in out
    # externaltest is installed, but it is not a dependent of libelf
    assert "externaltest" not in out


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_context_both_directions():
    """Tests that -C follows dependents and dependencies at the same time"""
    out = graph("--dot", "--installed", "-C", "1", "libdwarf")

    assert 'label="libdwarf@' in out
    # one level down
    assert 'label="libelf@' in out
    # one level up
    assert 'label="dyninst@' in out
    # two levels up
    assert "callpath" not in out


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_context_ascii():
    """Tests that the ascii output is pruned to the selected subgraph too"""
    out = graph("--ascii", "--installed", "-C", "1", "libdwarf")

    assert "libdwarf" in out and "libelf" in out and "dyninst" in out
    assert "callpath" not in out


@pytest.mark.db
@pytest.mark.usefixtures("mock_packages", "database")
def test_graph_context_errors():
    """Tests the invalid combinations of the context options"""
    # -C is a shorthand for -A and -B, so it cannot be combined with them
    with pytest.raises(SpackCommandError):
        graph("--dot", "-C", "1", "-A", "1", "dt-diamond")

    # the context options need a concrete DAG to walk
    with pytest.raises(SpackCommandError):
        graph("--static", "-A", "1", "dt-diamond")

    # negative levels make no sense
    with pytest.raises(SpackCommandError):
        graph("--dot", "-A", "-1", "dt-diamond")
