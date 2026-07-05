"""
Generates an SVG flowchart of the pay calculation order of operations.
Regenerate this diagram if the pay formula in pay_calculator.py changes.
"""


def generate_pay_logic_svg():
    """Build and return an SVG string showing the pay calculation pipeline."""
    # Dark theme colors matching the app
    bg = '#1e1e2e'
    block_bg = '#2a2a3e'
    block_border = '#4a9eff'
    arrow_color = '#6c7293'
    text_color = '#e0e0e0'
    label_color = '#a0a0b8'
    accent = '#4a9eff'

    block_width = 480
    block_height = 56
    wide_block_height = 88
    x_center = 300
    x_left = x_center - block_width // 2
    y_start = 30
    y_gap = 28  # gap between blocks (arrow space)
    arrow_head_size = 6
    font_size = 14
    label_font_size = 11

    steps = [
        {'text': 'Job Billing Amount', 'label': None},
        {'text': 'Subtract Expenses & Commissions', 'label': 'Job Net'},
        {'text': 'Subtract Tech Costs', 'label': 'Mileage + Per Diem + Personal Expenses'},
        {'text': '50% Pool Split', 'label': 'Tech Pool = Adjusted Net ÷ 2'},
        {'text': ['Single Tech: Pool ÷ Hours = Rate',
                  'Multi-Tech: Weight = (Min Rate × Hours) / Σ(all)',
                  'Base Pay = Pool × Weight'], 'label': 'Distribution', 'wide': True},
        {'text': 'Min Rate Floor Check', 'label': 'Use higher of: calculated rate vs minimum rate'},
        {'text': 'Base Pay = Hours × Effective Rate', 'label': None},
        {'text': 'Add: Mileage + Per Diem + Expenses + Reimbursables', 'label': 'Gross Pay'},
        {'text': 'Deduct Advances (FIFO, capped per period)', 'label': None},
        {'text': 'Net Payout', 'label': None},
    ]

    # Calculate positions
    blocks = []
    y = y_start
    for step in steps:
        is_wide = step.get('wide', False)
        h = wide_block_height if is_wide else block_height
        blocks.append({'x': x_left, 'y': y, 'w': block_width, 'h': h, **step})
        y += h + y_gap

    total_height = y + 10
    svg_width = 600

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {total_height}" '
                 f'width="{svg_width}" height="{total_height}" '
                 f'style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;">')

    # Background
    parts.append(f'<rect width="{svg_width}" height="{total_height}" fill="{bg}" rx="8"/>')

    # Arrow marker
    parts.append(f'<defs><marker id="arrowhead" markerWidth="{arrow_head_size}" '
                 f'markerHeight="{arrow_head_size}" refX="{arrow_head_size}" '
                 f'refY="{arrow_head_size // 2}" orient="auto">'
                 f'<polygon points="0 0, {arrow_head_size} {arrow_head_size // 2}, 0 {arrow_head_size}" '
                 f'fill="{arrow_color}"/></marker></defs>')

    for i, block in enumerate(blocks):
        bx, by, bw, bh = block['x'], block['y'], block['w'], block['h']

        # Draw block
        parts.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" '
                     f'rx="6" fill="{block_bg}" stroke="{block_border}" stroke-width="1.5"/>')

        # Draw text
        text = block['text']
        if isinstance(text, list):
            # Multi-line text for wide block
            line_height = 18
            text_y = by + (bh - len(text) * line_height) // 2 + font_size
            for j, line in enumerate(text):
                parts.append(f'<text x="{x_center}" y="{text_y + j * line_height}" '
                             f'text-anchor="middle" fill="{text_color}" '
                             f'font-size="{font_size}">{_escape(line)}</text>')
        else:
            text_y = by + bh // 2 + font_size // 2 - 1
            if block.get('label'):
                text_y = by + bh // 2 - 2
            parts.append(f'<text x="{x_center}" y="{text_y}" '
                         f'text-anchor="middle" fill="{text_color}" '
                         f'font-size="{font_size}" font-weight="500">{_escape(text)}</text>')

        # Draw label below main text
        if block.get('label') and not isinstance(text, list):
            label_y = by + bh // 2 + label_font_size + 4
            parts.append(f'<text x="{x_center}" y="{label_y}" '
                         f'text-anchor="middle" fill="{label_color}" '
                         f'font-size="{label_font_size}">{_escape(block["label"])}</text>')

        # Draw arrow to next block
        if i < len(blocks) - 1:
            arrow_x = x_center
            arrow_y1 = by + bh
            arrow_y2 = blocks[i + 1]['y']
            parts.append(f'<line x1="{arrow_x}" y1="{arrow_y1}" '
                         f'x2="{arrow_x}" y2="{arrow_y2}" '
                         f'stroke="{arrow_color}" stroke-width="2" '
                         f'marker-end="url(#arrowhead)"/>')

    parts.append('</svg>')
    return '\n'.join(parts)


def _escape(text):
    """Escape special characters for SVG XML."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
