class TextExporter:
    def __init__(self, lines):
        self.lines = lines

    def to_pdf(self, file_path):
        content_lines = []

        y_position = 700
        for line in self.lines:
            content_lines.extend([
                "BT",
                "/F1 12 Tf",
                f"20 {y_position} Td",
                f"({line}) Tj",
                "ET"
            ])
            y_position -= 20

        content = '\n'.join(content_lines)
        content_bytes = content.encode('utf-8')

        body = [
            "%PDF-1.4",
            "1 0 obj",
            "<< /Type /Catalog /Pages 2 0 R >>",
            "endobj",
            "2 0 obj",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "endobj",
            "3 0 obj",
            "<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>",
            "endobj",
            f"4 0 obj",
            f"<< /Length {len(content_bytes)} >>",
            "stream",
            content,
            "endstream",
            "endobj",
        ]

        body_bytes = '\n'.join(body).encode('utf-8')
        xref_position = len(body_bytes)

        xref_and_trailer = [
            "xref",
            "0 5",
            "0000000000 65535 f",
            "0000000010 00000 n",
            "0000000050 00000 n",
            "0000000100 00000 n",
            "0000000200 00000 n",
            "trailer",
            "<< /Size 5 /Root 1 0 R >>",
            "startxref",
            str(xref_position),
            "%%EOF"
        ]

        full_pdf = body + xref_and_trailer

        with open(file_path+'.pdf', 'wb') as f:
            f.write('\n'.join(full_pdf).encode('utf-8'))

    def to_html(self, file_path):
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Generated HTML</title>
        </head>
        <body>
            {''.join(f'<p>{line}</p>' for line in self.lines)}
        </body>
        </html>
        """

        with open(file_path+".html", 'w', encoding='utf-8') as f:
            f.write(html_content)

    def to_doc(self, file_path):
        header = r"{\rtf1\ansi\deff0"
        body = ""

        for line in self.lines:
            safe_line = line.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}')
            body += f"{safe_line}\\par\n"

        rtf_footer = "}"
        content = header + "\n" + body + rtf_footer

        with open(file_path+".doc", 'w', encoding='utf-8') as f:
            f.write(content)

