"""Side-effecting array indices are evaluated once by GLSL range analysis."""

import shutil
import subprocess

import pytest

import crosstl


def shader(stage, initial, index, followup="k"):
    body = (
        f"int k = {initial}; float vals[2]; "
        f"vals[{index}] = 1.0; vals[{followup}] = 2.0;"
    )
    if stage == "compute":
        return (
            "shader P { compute { "
            "layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in; "
            "buffer float* outp; void main() { "
            + body
            + " outp[0] = vals[0] + vals[1]; } } }"
        )
    return (
        "shader P { fragment { vec4 main() @ gl_FragColor { "
        + body
        + " return vec4(vals[0] + vals[1]); } } }"
    )


@pytest.mark.parametrize(("backend", "stage"), [("opengl", "compute"), ("webgl", "fragment")])
@pytest.mark.parametrize(("initial", "index"), [(0, "k++"), (1, "k--"), (0, "++k")])
def test_in_range_increment_is_not_counted_twice(tmp_path, backend, stage, initial, index):
    source = tmp_path / "increment.cgl"
    source.write_text(shader(stage, initial, index))
    output = crosstl.translate(str(source), backend=backend, format_output=False)
    assert output.count(index) == 1, output
    validator = shutil.which("glslangValidator")
    if validator:
        generated = tmp_path / ("output.comp" if stage == "compute" else "output.frag")
        generated.write_text(output)
        result = subprocess.run(
            [validator, "-S", "comp" if stage == "compute" else "frag", str(generated)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("backend", "stage"), [("opengl", "compute"), ("webgl", "fragment")])
def test_followup_out_of_bounds_is_still_rejected(tmp_path, backend, stage):
    source = tmp_path / "out_of_bounds.cgl"
    source.write_text(shader(stage, 1, "k++"))
    with pytest.raises(ValueError, match="constant index out of range"):
        crosstl.translate(str(source), backend=backend, format_output=False)


@pytest.mark.parametrize(("backend", "stage"), [("opengl", "compute"), ("webgl", "fragment")])
def test_ordinary_in_range_access_remains_valid(tmp_path, backend, stage):
    source = tmp_path / "plain.cgl"
    source.write_text(shader(stage, 0, "k"))
    output = crosstl.translate(str(source), backend=backend, format_output=False)
    assert "vals[k]" in output, output
