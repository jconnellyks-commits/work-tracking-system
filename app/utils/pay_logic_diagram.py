"""
Generates an SVG flowchart of the pay calculation order of operations.
Regenerate this diagram if the pay formula in pay_calculator.py changes.
"""


def generate_pay_logic_svg():
    """Build and return an SVG string showing the pay calculation pipeline."""
    bg = '#1e1e2e'
    block_bg = '#2a2a3e'
    block_border = '#4a9eff'
    arrow_color = '#6c7293'
    text_color = '#e0e0e0'
    label_color = '#a0a0b8'
    section_color = '#6c7293'
    adj_border = '#e0a030'

    block_width = 480
    block_height = 56
    wide_block_height = 88
    svg_width = 600
    x_center = svg_width // 2
    x_left = x_center - block_width // 2
    y_gap = 28
    arrow_head_size = 6
    font_size = 14
    label_font_size = 11
    section_font_size = 12

    main_steps = [
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

    adj_steps = [
        {'text': 'Job Billing or Time Entry Changed After Lock', 'label': None},
        {'text': 'Recalculate Pay vs Locked Snapshot', 'label': None},
        {'text': ['Difference > $0.01?',
                  'Yes → PayoutAdjustment created'], 'label': None, 'wide': True},
        {'text': ['Carry Forward → Bonus/Deduction in next period',
                  'Dismiss → No financial impact'], 'label': 'Manager resolves', 'wide': True},
    ]

    # Build block positions for main section
    y = 30
    main_blocks = []
    for step in main_steps:
        h = wide_block_height if step.get('wide') else block_height
        main_blocks.append({'x': x_left, 'y': y, 'w': block_width, 'h': h, **step})
        y += h + y_gap

    # Section divider
    divider_y = y + 10
    section_label_y = divider_y + 20
    y = section_label_y + 20

    # Build block positions for adjustment section
    adj_blocks = []
    for step in adj_steps:
        h = wide_block_height if step.get('wide') else block_height
        adj_blocks.append({'x': x_left, 'y': y, 'w': block_width, 'h': h, **step})
        y += h + y_gap

    total_height = y + 10

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {total_height}" '
                 f'width="{svg_width}" height="{total_height}" '
                 f'style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;">')

    parts.append(f'<rect width="{svg_width}" height="{total_height}" fill="{bg}" rx="8"/>')

    parts.append(f'<defs><marker id="arrowhead" markerWidth="{arrow_head_size}" '
                 f'markerHeight="{arrow_head_size}" refX="{arrow_head_size}" '
                 f'refY="{arrow_head_size // 2}" orient="auto">'
                 f'<polygon points="0 0, {arrow_head_size} {arrow_head_size // 2}, 0 {arrow_head_size}" '
                 f'fill="{arrow_color}"/></marker>'
                 f'<marker id="arrowhead-adj" markerWidth="{arrow_head_size}" '
                 f'markerHeight="{arrow_head_size}" refX="{arrow_head_size}" '
                 f'refY="{arrow_head_size // 2}" orient="auto">'
                 f'<polygon points="0 0, {arrow_head_size} {arrow_head_size // 2}, 0 {arrow_head_size}" '
                 f'fill="{adj_border}"/></marker></defs>')

    # Render main pipeline blocks
    _render_blocks(parts, main_blocks, x_center, block_border, block_bg,
                   text_color, label_color, arrow_color, font_size, label_font_size,
                   arrow_head_size, 'arrowhead')

    # Section divider line + label
    parts.append(f'<line x1="40" y1="{divider_y}" x2="{svg_width - 40}" y2="{divider_y}" '
                 f'stroke="{section_color}" stroke-width="1" stroke-dasharray="6,4"/>')
    parts.append(f'<text x="{x_center}" y="{section_label_y}" '
                 f'text-anchor="middle" fill="{section_color}" '
                 f'font-size="{section_font_size}" font-weight="600" '
                 f'letter-spacing="1">POST-LOCK ADJUSTMENTS</text>')

    # Render adjustment blocks with different border color
    _render_blocks(parts, adj_blocks, x_center, adj_border, block_bg,
                   text_color, label_color, adj_border, font_size, label_font_size,
                   arrow_head_size, 'arrowhead-adj')

    parts.append('</svg>')
    return '\n'.join(parts)


def _render_blocks(parts, blocks, x_center, border_color, fill_color,
                   text_color, label_color, arrow_color, font_size, label_font_size,
                   arrow_head_size, marker_id):
    for i, block in enumerate(blocks):
        bx, by, bw, bh = block['x'], block['y'], block['w'], block['h']

        parts.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" '
                     f'rx="6" fill="{fill_color}" stroke="{border_color}" stroke-width="1.5"/>')

        text = block['text']
        if isinstance(text, list):
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

        if block.get('label') and not isinstance(text, list):
            label_y = by + bh // 2 + label_font_size + 4
            parts.append(f'<text x="{x_center}" y="{label_y}" '
                         f'text-anchor="middle" fill="{label_color}" '
                         f'font-size="{label_font_size}">{_escape(block["label"])}</text>')

        if i < len(blocks) - 1:
            arrow_y1 = by + bh
            arrow_y2 = blocks[i + 1]['y']
            parts.append(f'<line x1="{x_center}" y1="{arrow_y1}" '
                         f'x2="{x_center}" y2="{arrow_y2}" '
                         f'stroke="{arrow_color}" stroke-width="2" '
                         f'marker-end="url(#{marker_id})"/>')


def _escape(text):
    """Escape special characters for SVG XML."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
