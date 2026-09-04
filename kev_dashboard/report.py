"""Self-contained HTML reporting for KEV analysis."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .export import atomic_write_text


def _escape(value: Any) -> str:
    """Convert a value to safely escaped HTML text."""

    return escape(
        str(value),
        quote=True,
    )


def _short_label(
    label: str,
    *,
    maximum: int = 30,
) -> str:
    """Shorten long visible SVG labels without losing source data."""

    if len(label) <= maximum:
        return label

    return label[: maximum - 1] + "…"


def _metric(
    label: str,
    value: str,
    detail: str,
) -> str:
    """Render one dashboard metric card."""

    return (
        '<article class="metric">'
        f'<p class="metric-label">{_escape(label)}</p>'
        f'<p class="metric-value">{_escape(value)}</p>'
        f'<p class="metric-detail">{_escape(detail)}</p>'
        "</article>"
    )


def _chart_data_table(
    title: str,
    rows: list[tuple[str, int]],
) -> str:
    """Render a text equivalent for an SVG chart."""

    body = "".join(
        (
            "<tr>"
            f"<th scope=\"row\">{_escape(label)}</th>"
            f"<td>{value:,}</td>"
            "</tr>"
        )
        for label, value in rows
    )

    return (
        '<details class="chart-data">'
        f"<summary>View data for {_escape(title)}</summary>"
        '<div class="table-scroll">'
        "<table>"
        "<thead>"
        "<tr><th scope=\"col\">Category</th>"
        "<th scope=\"col\">Count</th></tr>"
        "</thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
        "</details>"
    )


def _bar_chart(
    chart_id: str,
    title: str,
    rows: list[tuple[str, int]],
    *,
    color: str,
) -> str:
    """Render an accessible horizontal SVG bar chart."""

    if any(value < 0 for _, value in rows):
        raise ValueError(
            "chart values cannot be negative"
        )

    maximum_value = max(
        (value for _, value in rows),
        default=1,
    )

    if maximum_value == 0:
        maximum_value = 1

    width = 760
    label_width = 235
    chart_width = 420
    row_height = 34
    height = max(
        82,
        52 + len(rows) * row_height,
    )

    elements: list[str] = []

    for index, (label, value) in enumerate(rows):
        y_position = 38 + index * row_height

        bar_width = (
            round(value / maximum_value * chart_width)
            if value
            else 0
        )

        value_x = label_width + bar_width + 10
        visible_label = _short_label(label)

        elements.extend(
            [
                (
                    f'<text x="0" y="{y_position + 15}" '
                    'class="chart-label">'
                    f"{_escape(visible_label)}</text>"
                ),
                (
                    f'<rect x="{label_width}" '
                    f'y="{y_position}" '
                    f'width="{bar_width}" '
                    'height="20" rx="4" '
                    f'fill="{_escape(color)}">'
                    f"<title>{_escape(label)}: "
                    f"{value:,}</title></rect>"
                ),
                (
                    f'<text x="{value_x}" '
                    f'y="{y_position + 15}" '
                    'class="chart-value">'
                    f"{value:,}</text>"
                ),
            ]
        )

    if rows:
        description = "; ".join(
            f"{label}: {value}"
            for label, value in rows
        )
    else:
        description = "No data is available for this chart."

    svg_title_id = f"{chart_id}-title"
    svg_description_id = f"{chart_id}-description"
    caption_id = f"{chart_id}-caption"

    return (
        '<figure class="chart" '
        f'aria-labelledby="{caption_id}">'
        f'<figcaption id="{caption_id}">'
        f"{_escape(title)}</figcaption>"
        f'<svg viewBox="0 0 {width} {height}" '
        'role="img" '
        f'aria-labelledby="{svg_title_id} '
        f'{svg_description_id}">'
        f'<title id="{svg_title_id}">'
        f"{_escape(title)}</title>"
        f'<desc id="{svg_description_id}">'
        f"{_escape(description)}</desc>"
        + "".join(elements)
        + "</svg>"
        + _chart_data_table(title, rows)
        + "</figure>"
    )


def _source_markup(source: str) -> str:
    """Render HTTPS sources as links and local sources as code."""

    parsed = urlparse(source)

    if (
        parsed.scheme.casefold() == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    ):
        safe_source = _escape(source)

        return (
            f'<a href="{safe_source}" '
            'rel="noreferrer noopener">'
            f"{safe_source}</a>"
        )

    return (
        "local snapshot "
        f"<code>{_escape(source)}</code>"
    )


def _queue_rows(
    analysis: dict[str, Any],
    *,
    queue_limit: int,
) -> str:
    """Render the first rows in the ordered review queue."""

    rendered_rows: list[str] = []

    for row in analysis["vulnerabilities"][:queue_limit]:
        reasons = "; ".join(
            row["review_reasons"]
        )

        rendered_rows.append(
            "<tr>"
            f'<td><code>{_escape(row["cve_id"])}</code></td>'
            f'<td>{_escape(row["vendor"])}</td>'
            f'<td>{_escape(row["product"])}</td>'
            f'<td>{_escape(row["ransomware_use"])}</td>'
            f'<td>{_escape(row["forensic_triage"])}</td>'
            f'<td><time datetime="{_escape(row["due_date"])}">'
            f'{_escape(row["due_date"])}</time></td>'
            "<td>"
            '<span class="signal">'
            f'{_escape(row["primary_review_signal"])}'
            "</span>"
            '<span class="reasons">'
            f"{_escape(reasons)}"
            "</span>"
            "</td>"
            "</tr>"
        )

    return "".join(rendered_rows)


def build_report_html(
    analysis: dict[str, Any],
    *,
    top_vendors: int = 10,
    queue_limit: int = 20,
) -> str:
    """Build a complete self-contained HTML dashboard."""

    if top_vendors < 1:
        raise ValueError(
            "top_vendors must be at least 1"
        )

    if queue_limit < 1:
        raise ValueError(
            "queue_limit must be at least 1"
        )

    metadata = analysis["metadata"]
    headline = analysis["headline"]
    remediation = analysis[
        "remediation_window_statistics"
    ]

    displayed_vendors = analysis["vendors"][
        :top_vendors
    ]

    metrics = "".join(
        [
            _metric(
                "Catalog entries",
                f'{headline["total_vulnerabilities"]:,}',
                "Entries in this source snapshot",
            ),
            _metric(
                "Known ransomware",
                f'{headline["known_ransomware"]:,}',
                (
                    f'{headline["known_ransomware_percent"]:.1f}% '
                    "of the snapshot"
                ),
            ),
            _metric(
                "Forensic triage",
                f'{headline["forensic_triage"]:,}',
                (
                    f'{headline["forensic_triage_percent"]:.1f}% '
                    "marked Yes"
                ),
            ),
            _metric(
                "Unique vendors",
                f'{headline["unique_vendors"]:,}',
                "Using vendor names published in the source",
            ),
            _metric(
                "Median window",
                (
                    f'{headline["median_remediation_days"]:g} '
                    "days"
                ),
                (
                    f'Mean {remediation["mean_days"]:g}; '
                    f'range {remediation["minimum_days"]}'
                    f'–{remediation["maximum_days"]}'
                ),
            ),
        ]
    )

    charts = "".join(
        [
            _bar_chart(
                "vendor-chart",
                (
                    f"Top {len(displayed_vendors)} vendors "
                    "by catalog entries"
                ),
                [
                    (row["vendor"], row["count"])
                    for row in displayed_vendors
                ],
                color="#38bdf8",
            ),
            _bar_chart(
                "year-chart",
                "Catalog additions by year",
                [
                    (str(row["year"]), row["count"])
                    for row in analysis["years"]
                ],
                color="#a78bfa",
            ),
            _bar_chart(
                "ransomware-chart",
                "Known ransomware campaign use",
                [
                    (row["status"], row["count"])
                    for row in analysis["ransomware"]
                ],
                color="#fb7185",
            ),
            _bar_chart(
                "forensic-chart",
                "Forensic-triage indication",
                [
                    (row["status"], row["count"])
                    for row in analysis["forensic_triage"]
                ],
                color="#fbbf24",
            ),
            _bar_chart(
                "remediation-chart",
                "Catalog remediation-window distribution",
                [
                    (row["window"], row["count"])
                    for row in analysis[
                        "remediation_buckets"
                    ]
                ],
                color="#34d399",
            ),
            _bar_chart(
                "review-chart",
                "Primary review signals",
                [
                    (row["signal"], row["count"])
                    for row in analysis["review_signals"]
                ],
                color="#22d3ee",
            ),
        ]
    )

    queue_rows = _queue_rows(
        analysis,
        queue_limit=queue_limit,
    )

    source = _source_markup(
        str(metadata["source"])
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
  >
  <title>CISA KEV Prioritization Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --background: #07111f;
      --panel: #101d2d;
      --panel-raised: #15263a;
      --border: #2a3e55;
      --text: #e7eef7;
      --muted: #a7b7c9;
      --accent: #38bdf8;
      --warning: #fbbf24;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--background);
      color: var(--text);
      font-family:
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
      font-size: 16px;
      line-height: 1.55;
    }}

    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 48px 0 80px;
    }}

    header {{
      margin-bottom: 28px;
    }}

    h1 {{
      max-width: 900px;
      margin: 8px 0 16px;
      font-size: clamp(2rem, 5vw, 3.5rem);
      line-height: 1.08;
    }}

    h2 {{
      margin: 48px 0 16px;
      font-size: 1.65rem;
    }}

    p {{
      margin-top: 0;
    }}

    a {{
      color: #7dd3fc;
    }}

    code {{
      color: #bae6fd;
    }}

    .eyebrow {{
      margin: 0;
      color: var(--accent);
      font-size: 0.85rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}

    .lede {{
      max-width: 80ch;
      color: var(--muted);
      font-size: 1.08rem;
    }}

    .source-line {{
      color: var(--muted);
      overflow-wrap: anywhere;
    }}

    .notice {{
      margin: 24px 0;
      padding: 18px;
      background: var(--panel-raised);
      border: 1px solid var(--border);
      border-left: 5px solid var(--warning);
      border-radius: 8px;
    }}

    .metrics {{
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
    }}

    .metric {{
      min-width: 0;
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }}

    .metric-label,
    .metric-detail {{
      margin: 0;
      color: var(--muted);
    }}

    .metric-value {{
      margin: 5px 0;
      font-size: 2rem;
      font-weight: 760;
    }}

    .charts {{
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(430px, 1fr));
      gap: 16px;
    }}

    .chart {{
      min-width: 0;
      margin: 0;
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }}

    figcaption {{
      margin-bottom: 8px;
      font-weight: 720;
    }}

    svg {{
      display: block;
      width: 100%;
      height: auto;
      overflow: visible;
    }}

    .chart-label,
    .chart-value {{
      fill: var(--text);
      font-size: 13px;
    }}

    .chart-data {{
      margin-top: 12px;
      color: var(--muted);
    }}

    .chart-data summary {{
      cursor: pointer;
    }}

    .table-scroll {{
      width: 100%;
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
    }}

    th,
    td {{
      padding: 11px 13px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--border);
    }}

    thead th {{
      color: var(--muted);
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    tbody tr:hover {{
      background: var(--panel-raised);
    }}

    .queue {{
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}

    .signal {{
      display: block;
      font-weight: 700;
      white-space: nowrap;
    }}

    .reasons {{
      display: block;
      max-width: 42ch;
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.85rem;
    }}

    footer {{
      margin-top: 52px;
      padding-top: 22px;
      color: var(--muted);
      border-top: 1px solid var(--border);
    }}

    @media (max-width: 700px) {{
      main {{
        width: min(100% - 20px, 1180px);
        padding-top: 28px;
      }}

      .charts {{
        grid-template-columns: 1fr;
      }}

      .metric-value {{
        font-size: 1.7rem;
      }}
    }}

    @media print {{
      :root {{
        color-scheme: light;
        --background: #ffffff;
        --panel: #ffffff;
        --panel-raised: #f5f7fa;
        --border: #cbd5e1;
        --text: #111827;
        --muted: #4b5563;
        --accent: #0369a1;
        --warning: #92400e;
      }}

      main {{
        width: 100%;
        padding: 0;
      }}

      .chart,
      .metric,
      .queue {{
        break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Vulnerability intelligence</p>
      <h1>CISA KEV Prioritization Dashboard</h1>
      <p class="lede">
        A reproducible analysis of catalog trends, ransomware
        associations, forensic-triage indications, remediation
        windows, and transparent review signals.
      </p>
      <p class="source-line">
        Source: {source}<br>
        Analysis date:
        <strong>{_escape(metadata["as_of"])}</strong> ·
        Catalog version:
        <strong>{_escape(metadata["catalog_version"])}</strong> ·
        Released:
        <strong>{_escape(metadata["date_released"])}</strong>
      </p>
    </header>

    <aside class="notice">
      <strong>Interpretation:</strong>
      This ordering is a workflow aid, not a universal risk or
      severity score. Final remediation decisions require asset
      ownership, affected-version confirmation, exposure, business
      impact, compensating controls, and local threat intelligence.
      A passed catalog due date does not prove that a particular
      organization remains vulnerable or is noncompliant.
    </aside>

    <section aria-labelledby="headline-heading">
      <h2 id="headline-heading">Snapshot overview</h2>
      <div class="metrics">
        {metrics}
      </div>
    </section>

    <section aria-labelledby="trends-heading">
      <h2 id="trends-heading">Catalog trends</h2>
      <div class="charts">
        {charts}
      </div>
    </section>

    <section aria-labelledby="queue-heading">
      <h2 id="queue-heading">Operational review queue</h2>
      <p class="lede">
        Displaying the first
        {min(queue_limit, len(analysis["vulnerabilities"]))}
        of {len(analysis["vulnerabilities"]):,} records.
        The complete normalized dataset is available in
        <code>data/vulnerabilities.csv</code>.
      </p>

      <div class="table-scroll queue">
        <table>
          <caption>
            Vulnerabilities ordered by documented review signals
          </caption>
          <thead>
            <tr>
              <th scope="col">CVE</th>
              <th scope="col">Vendor</th>
              <th scope="col">Product</th>
              <th scope="col">Ransomware</th>
              <th scope="col">Forensic triage</th>
              <th scope="col">Due date</th>
              <th scope="col">Review rationale</th>
            </tr>
          </thead>
          <tbody id="review-queue-body">
            {queue_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="method-heading">
      <h2 id="method-heading">Method and responsible use</h2>
      <p class="lede">
        Required fields and dates are validated before analysis.
        Unknown ransomware status is preserved as Unknown rather
        than interpreted as evidence of no ransomware activity.
        Vendor counts reflect catalog naming and are not vendor
        market-share or product-quality measurements.
      </p>
    </section>

    <footer>
      Independent analysis of public CISA data. This project is not
      affiliated with or endorsed by CISA. Review the repository's
      methodology before using these results operationally.
    </footer>
  </main>
</body>
</html>
"""

    return html


def render_report(
    analysis: dict[str, Any],
    output_path: Path,
    *,
    top_vendors: int = 10,
    queue_limit: int = 20,
) -> Path:
    """Build and atomically write the HTML dashboard."""

    html = build_report_html(
        analysis,
        top_vendors=top_vendors,
        queue_limit=queue_limit,
    )

    atomic_write_text(
        output_path,
        html,
    )

    return output_path