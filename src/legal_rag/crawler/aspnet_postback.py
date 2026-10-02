"""Pure parsing/formatting helpers for driving ASP.NET WebForms GridView postbacks.

vanban.chinhphu.vn paginates its document listings via `__doPostBack` calls
(GridView `Page$N` paging), not via a `?page=N` query string — a `?pg=N` on
the URL is silently ignored by the server. Furthermore, postback requests
require all active form inputs/selects from `<form id="form1">` (specifically
state fields like `hidSiteId`, `hidIsSearch`, `hiIsTrangTTG`, viewstate, etc.);
posting only the 5 minimal ASP.NET fields causes the server to return an empty
table with "Không có thông tin văn bản!".

These helpers read all form fields out of a rendered page and build the complete
POST body needed to request the next page.
"""

from __future__ import annotations

import html as html_lib
import re

_HIDDEN_FIELD_NAMES = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")


def extract_form_fields(html: str) -> dict[str, str]:
    """Read all input and select fields inside <form id="form1"> for ASP.NET postback.

    Excludes submit, button, image, checkbox, and radio inputs.
    For select elements, picks the selected option value (or the first option value).
    All extracted values have HTML entities decoded.
    """
    form_match = re.search(r'<form\b[^>]*\bid=["\']form1["\'][^>]*>(.*?)</form>', html, re.I | re.S)
    if not form_match:
        return {}

    form_content = form_match.group(1)
    fields: dict[str, str] = {}

    for input_match in re.finditer(r'<input\b(?P<attrs>[^>]*)>', form_content, re.I):
        attrs = input_match.group("attrs")
        type_match = re.search(r'\btype=["\']([^"\']*)["\']', attrs, re.I)
        input_type = type_match.group(1).lower() if type_match else "text"
        if input_type in ("submit", "button", "image", "checkbox", "radio"):
            continue
        name_match = re.search(r'\bname=["\']([^"\']*)["\']', attrs, re.I)
        if not name_match:
            continue
        name = name_match.group(1)
        val_match = re.search(r'\bvalue=["\']([^"\']*)["\']', attrs, re.I)
        val = val_match.group(1) if val_match else ""
        fields[name] = html_lib.unescape(val)

    for textarea_match in re.finditer(r'<textarea\b(?P<attrs>[^>]*)>(?P<body>.*?)</textarea>', form_content, re.I | re.S):
        attrs = textarea_match.group("attrs")
        name_match = re.search(r'\bname=["\']([^"\']*)["\']', attrs, re.I)
        if not name_match:
            continue
        name = name_match.group(1)
        val = textarea_match.group("body")
        fields[name] = html_lib.unescape(val)

    for select_match in re.finditer(r'<select\b(?P<attrs>[^>]*)>(?P<body>.*?)</select>', form_content, re.I | re.S):
        attrs = select_match.group("attrs")
        body = select_match.group("body")
        name_match = re.search(r'\bname=["\']([^"\']*)["\']', attrs, re.I)
        if not name_match:
            continue
        name = name_match.group(1)
        options = list(re.finditer(r'<option\b(?P<opt_attrs>[^>]*)>(?P<opt_text>.*?)</option>', body, re.I | re.S))
        selected_val: str | None = None
        first_val: str | None = None
        for i, opt in enumerate(options):
            opt_attrs = opt.group("opt_attrs")
            val_match = re.search(r'\bvalue=["\']([^"\']*)["\']', opt_attrs, re.I)
            val = val_match.group(1) if val_match else opt.group("opt_text").strip()
            val = html_lib.unescape(val)
            if i == 0:
                first_val = val
            if re.search(r'\bselected\b', opt_attrs, re.I):
                selected_val = val
                break
        fields[name] = selected_val if selected_val is not None else (first_val if first_val is not None else "")

    return fields


def extract_hidden_fields(html: str) -> dict[str, str]:
    """Read the ASP.NET postback state fields out of a rendered page (kept for compatibility)."""
    fields: dict[str, str] = {}
    for name in _HIDDEN_FIELD_NAMES:
        match = re.search(rf'id="{name}"[^>]*value="([^"]*)"', html)
        fields[name] = html_lib.unescape(match.group(1)) if match else ""
    return fields


def find_control_prefix(html: str, control_suffix: str) -> str | None:
    """Find the dynamic `ctrl_NNNNN_NNN` prefix ASP.NET generated for a named control."""
    match = re.search(rf"(ctrl_\d+_\d+)\${re.escape(control_suffix)}", html)
    return match.group(1) if match else None


def extract_page_targets(html: str) -> list[str]:
    """Return the pager's page targets (e.g. ['2', '3', '4', '5', 'Last']), deduplicated, in document order."""
    seen: list[str] = []
    for target in re.findall(r"Page\$(\d+|Last)", html):
        if target not in seen:
            seen.append(target)
    return seen


def build_page_postback_data(
    form_fields: dict[str, str], prefix: str, grid_suffix: str, page_target: str
) -> dict[str, str]:
    """Build the POST body that requests a given GridView page via __doPostBack.

    Overwrites __EVENTTARGET and __EVENTARGUMENT while preserving all other
    form fields (e.g. hidSiteId, hidIsSearch, hiIsTrangTTG, viewstate, etc.).
    """
    data = dict(form_fields)
    data["__EVENTTARGET"] = f"{prefix}${grid_suffix}"
    data["__EVENTARGUMENT"] = f"Page${page_target}"
    return data
