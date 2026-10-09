"""Apply only the GIL binding change to an archived baseline source snapshot.

This is for a running binary whose source predates the checkout. It copies the
archive to a NEW path, preserving its combat semantics and Cargo.lock. No
snapshot, source checkout, or binary is modified in place.
"""
import argparse
from pathlib import Path
import shutil


def extract(source, name):
    pos = source.index("    fn " + name + "(")
    start = pos
    while True:
        previous = source.rfind("\n", 0, start-1)+1
        if source[previous:start].strip().startswith(("#[", "///")):
            start = previous
        else:
            break
    opening = source.index("{", pos)
    depth, end = 1, opening+1
    while depth:
        if source[end] == "{": depth += 1
        if source[end] == "}": depth -= 1
        end += 1
    return source[:start]+source[end:], source[pos:end]


def stage(archive, output):
    here = Path(__file__).resolve().parent
    if output.exists():
        raise ValueError("output must be a new source directory")
    output.mkdir(parents=True)
    target = output/"engine-rs"
    shutil.copytree(archive, target)
    for filename in ("build.rs", "build_quickwins.sh"):
        shutil.copy2(here/filename, target/filename)
    manifest = target/"Cargo.toml"
    text = manifest.read_text()
    assert "gil-release" not in text
    manifest.write_text(text.replace('[features]\n', '[features]\ngil-release = []\n', 1))
    for filename, cls, names in (
        ("lib.rs", "BattleState", ("step", "apply_action")),
        ("scripts.rs", "NativeScripts", ("select_action", "apply_discrete", "evaluate", "rollout")),
    ):
        path = target/"src"/filename
        source = path.read_text()
        helpers = []
        wrappers = []
        current = (here/"src"/filename).read_text()
        for name in names:
            source, helper = extract(source, name)
            helpers.append(helper)
            start = current.index('    #[pyo3(name = "'+name+'"')
            _, wrapper = extract(current, name+"_detached")
            end = current.index("    fn "+name+"_detached(", start)
            wrappers.append(current[start:end]+wrapper)
        marker = '#[pymethods]\nimpl '+cls+' {\n'
        assert source.count(marker) == 1
        source = source.replace(marker, marker+"\n".join(wrappers)+"\n", 1)
        source += '\nimpl '+cls+' {\n'+"\n".join(helpers)+'\n}\n'
        if filename == "lib.rs":
            source += current[current.index("// Compile-time opt-in; the baseline binding retains the GIL."):]
        path.write_text(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="archived engine-rs source directory")
    parser.add_argument("new_output", type=Path, help="new project root (containing engine-rs)")
    args = parser.parse_args()
    stage(args.archive, args.new_output)
