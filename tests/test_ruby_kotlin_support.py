from pathlib import Path

from n3mo.core import symbol_extractor


def _write_source(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_ruby_and_kotlin_parsers_are_loaded():
    assert symbol_extractor.get_parser("ruby") is not None
    assert symbol_extractor.get_parser("kotlin") is not None


def test_ruby_extensions_route_to_ruby_parser(tmp_path, monkeypatch):
    seen = []

    def fake_extract_generic(code_bytes, file_path, lang_name):
        seen.append((Path(file_path).suffix, lang_name))
        return [], [], []

    monkeypatch.setattr(symbol_extractor, "extract_generic", fake_extract_generic)

    for name in ("sample.rb", "sample.rbw"):
        symbol_extractor.extract_symbols(str(_write_source(tmp_path, name, "puts 'hello'\n")))

    assert seen == [(".rb", "ruby"), (".rbw", "ruby")]


def test_kotlin_extensions_route_to_kotlin_parser(tmp_path, monkeypatch):
    seen = []

    def fake_extract_generic(code_bytes, file_path, lang_name):
        seen.append((Path(file_path).suffix, lang_name))
        return [], [], []

    monkeypatch.setattr(symbol_extractor, "extract_generic", fake_extract_generic)

    for name in ("Sample.kt", "build.kts"):
        symbol_extractor.extract_symbols(str(_write_source(tmp_path, name, "fun main() {}\n")))

    assert seen == [(".kt", "kotlin"), (".kts", "kotlin")]


def test_kotlin_extraction_covers_class_function_and_call(tmp_path):
    path = _write_source(
        tmp_path,
        "Sample.kt",
        """
class Greeter {
    fun greet() {
        println("hello")
    }
}
""",
    )

    symbols, _, calls = symbol_extractor.extract_symbols(str(path))

    symbol_names = {symbol["name"] for symbol in symbols}
    call_names = {call["call_name"] for call in calls}

    assert "Greeter" in symbol_names
    assert "greet" in symbol_names
    assert "println" in call_names
