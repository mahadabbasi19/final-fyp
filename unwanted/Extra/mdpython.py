import pypandoc

# Download pandoc automatically (one-time)
pypandoc.download_pandoc()

input_md = "CODE_DOCUMENTATION_FOR_VIVA.md"
output_docx = "output.docx"

pypandoc.convert_file(
    input_md,
    'docx',
    outputfile=output_docx
)

print("Markdown converted to Word successfully!")
