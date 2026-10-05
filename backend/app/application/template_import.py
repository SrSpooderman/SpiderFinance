"""Compatibility entrypoint for the template import command."""

from app.modules.imports.template_adapter import TemplateData, import_template, main, read_template

__all__ = ["TemplateData", "import_template", "main", "read_template"]

if __name__ == "__main__":
    main()
