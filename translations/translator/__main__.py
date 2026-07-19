import typer
from . import ai_prepare, ai_translate, compile_dict, extract_pot, merge_po

app = typer.Typer()
app.add_typer(extract_pot.app)
app.add_typer(merge_po.app)
app.add_typer(ai_prepare.app)
app.add_typer(ai_translate.app)
app.add_typer(compile_dict.app)


if __name__ == "__main__":
    app()
