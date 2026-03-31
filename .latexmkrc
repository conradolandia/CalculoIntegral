# Configuración de latexmk para LuaLaTeX con natbib/BibTeX
$pdflatex = 'lualatex --shell-escape %O %S';
$pdf_mode = 5;  # LuaLaTeX mode
$bibtex_use = 1;  # Use bibtex (para natbib)
