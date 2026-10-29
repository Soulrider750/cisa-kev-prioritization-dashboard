(() => {
  "use strict";

  const PAGE_SIZE = 25;
  const DATA_URL = "data/kev_snapshot.json";

  const elements = {
    form: document.getElementById("filters"),
    fieldset: document.getElementById("filter-fields"),
    query: document.getElementById("query"),
    cve: document.getElementById("cve"),
    vendor: document.getElementById("vendor"),
    product: document.getElementById("product"),
    ransomware: document.getElementById("ransomware"),
    cwe: document.getElementById("cwe"),
    dateFrom: document.getElementById("date-from"),
    dateTo: document.getElementById("date-to"),
    catalogMeta: document.getElementById("catalog-meta"),
    resultCount: document.getElementById("result-count"),
    results: document.getElementById("results"),
    empty: document.getElementById("empty"),
    error: document.getElementById("error"),
    retry: document.getElementById("retry"),
    pagination: document.getElementById("pagination"),
    previous: document.getElementById("previous"),
    next: document.getElementById("next"),
    pageStatus: document.getElementById("page-status"),
  };

  let entries = [];
  let matches = [];
  let page = 1;

  function text(value) {
    if (value === null || value === undefined) {
      return "";
    }
    return String(value);
  }

  function folded(value) {
    return text(value).trim().toLowerCase();
  }

  function searchableText(value) {
    if (Array.isArray(value)) {
      return value.map(searchableText).join(" ");
    }
    if (value !== null && typeof value === "object") {
      return Object.values(value).map(searchableText).join(" ");
    }
    return text(value);
  }

  function makeElement(tagName, className, content) {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (content !== undefined) {
      node.textContent = text(content);
    }
    return node;
  }

  function addFact(list, label, value) {
    const wrapper = document.createElement("div");
    wrapper.appendChild(makeElement("dt", "", label));
    wrapper.appendChild(makeElement("dd", "", value || "Not supplied"));
    list.appendChild(wrapper);
  }

  function trimNoteUrl(value) {
    let end = value.length;
    while (end > 0) {
      const candidate = value.slice(0, end);
      const last = candidate.slice(-1);
      if (/[.,;:!?]/.test(last)) {
        end -= 1;
      } else if (
        (last === ")" &&
          (candidate.match(/\)/g) || []).length >
            (candidate.match(/\(/g) || []).length) ||
        (last === "]" &&
          (candidate.match(/\]/g) || []).length >
            (candidate.match(/\[/g) || []).length) ||
        (last === "}" &&
          (candidate.match(/\}/g) || []).length >
            (candidate.match(/\{/g) || []).length)
      ) {
        end -= 1;
      } else {
        break;
      }
    }
    return value.slice(0, end);
  }

  function addNotes(list, value) {
    const wrapper = document.createElement("div");
    wrapper.appendChild(makeElement("dt", "", "Notes"));
    const detail = makeElement("dd");
    const notes = text(value) || "Not supplied";
    const urlPattern = /\bhttps?:\/\/[^\s<>"']+/gi;
    let position = 0;

    for (const match of notes.matchAll(urlPattern)) {
      const rawUrl = match[0];
      const urlText = trimNoteUrl(rawUrl);
      detail.appendChild(
        document.createTextNode(notes.slice(position, match.index))
      );

      try {
        const parsedUrl = new URL(urlText);
        if (
          (parsedUrl.protocol !== "http:" &&
            parsedUrl.protocol !== "https:") ||
          !parsedUrl.hostname ||
          parsedUrl.username ||
          parsedUrl.password ||
          /[\\\u0000-\u001f\u007f]/.test(urlText)
        ) {
          throw new TypeError("Unsafe note URL");
        }
        const link = makeElement("a", "", urlText);
        link.href = parsedUrl.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        detail.appendChild(link);
      } catch (_error) {
        detail.appendChild(document.createTextNode(urlText));
      }

      detail.appendChild(document.createTextNode(rawUrl.slice(urlText.length)));
      position = match.index + rawUrl.length;
    }

    detail.appendChild(document.createTextNode(notes.slice(position)));
    wrapper.appendChild(detail);
    list.appendChild(wrapper);
  }

  function renderEntry(entry) {
    const record = entry.record;
    const article = makeElement("article", "record");
    const heading = makeElement("h3", "record-heading");
    const cve = makeElement("code", "", record.cveID);
    const name = makeElement(
      "span",
      "record-name",
      record.vulnerabilityName
    );
    heading.appendChild(cve);
    heading.appendChild(name);
    article.appendChild(heading);

    const facts = makeElement("dl", "record-facts");
    addFact(facts, "Vendor", record.vendorProject);
    addFact(facts, "Product", record.product);
    addFact(
      facts,
      "Ransomware campaign use",
      record.knownRansomwareCampaignUse
    );
    addFact(facts, "Date added", record.dateAdded);
    addFact(facts, "Due date", record.dueDate);
    article.appendChild(facts);

    const details = document.createElement("details");
    details.appendChild(makeElement("summary", "", "View catalog details"));
    const detailList = makeElement("dl", "record-details");
    addFact(detailList, "Description", record.shortDescription);
    addFact(detailList, "Required action", record.requiredAction);
    addFact(
      detailList,
      "Forensic triage",
      record.forensicTriage
    );
    addFact(
      detailList,
      "CWE",
      Array.isArray(record.cwes) ? record.cwes.join(", ") : ""
    );
    addNotes(detailList, record.notes);
    details.appendChild(detailList);
    article.appendChild(details);

    return article;
  }

  function currentFilters() {
    return {
      query: folded(elements.query.value),
      cve: folded(elements.cve.value),
      vendor: folded(elements.vendor.value),
      product: folded(elements.product.value),
      ransomware: folded(elements.ransomware.value),
      cwe: folded(elements.cwe.value),
      dateFrom: elements.dateFrom.value,
      dateTo: elements.dateTo.value,
    };
  }

  function includes(value, query) {
    return !query || folded(value).includes(query);
  }

  function entryMatches(entry, filters) {
    const record = entry.record;
    const cwes = Array.isArray(record.cwes) ? record.cwes.join(" ") : "";
    const dateAdded = text(record.dateAdded);

    return (
      (!filters.query || entry.searchText.includes(filters.query)) &&
      includes(record.cveID, filters.cve) &&
      includes(record.vendorProject, filters.vendor) &&
      includes(record.product, filters.product) &&
      (!filters.ransomware ||
        folded(record.knownRansomwareCampaignUse) === filters.ransomware) &&
      includes(cwes, filters.cwe) &&
      (!filters.dateFrom || dateAdded >= filters.dateFrom) &&
      (!filters.dateTo || dateAdded <= filters.dateTo)
    );
  }

  function renderResults() {
    const total = matches.length;
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    page = Math.min(Math.max(1, page), pageCount);
    elements.resultCount.textContent =
      total.toLocaleString() + " of " +
      entries.length.toLocaleString() + " entries match";

    elements.empty.hidden = total !== 0;
    elements.results.hidden = total === 0;
    elements.pagination.hidden = pageCount <= 1 || total === 0;

    const start = (page - 1) * PAGE_SIZE;
    const fragment = document.createDocumentFragment();
    for (const entry of matches.slice(start, start + PAGE_SIZE)) {
      fragment.appendChild(renderEntry(entry));
    }
    elements.results.replaceChildren(fragment);

    elements.pageStatus.textContent =
      "Page " + page + " of " + pageCount;
    elements.previous.disabled = page <= 1;
    elements.next.disabled = page >= pageCount;
  }

  function applyFilters() {
    const filters = currentFilters();
    matches = entries.filter((entry) => entryMatches(entry, filters));
    renderResults();
  }

  async function loadCatalog() {
    elements.fieldset.disabled = true;
    elements.error.hidden = true;
    elements.empty.hidden = true;
    elements.pagination.hidden = true;
    elements.results.replaceChildren();
    elements.resultCount.textContent = "Loading catalog…";
    elements.catalogMeta.textContent = "Loading catalog details…";

    try {
      const response = await fetch(DATA_URL, {
        mode: "same-origin",
        credentials: "omit",
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("Catalog request failed");
      }

      const payload = await response.json();
      const records = payload && payload.vulnerabilities;
      if (
        !Array.isArray(records) ||
        !Number.isSafeInteger(payload.count) ||
        payload.count < 1 ||
        payload.count !== records.length ||
        records.some(
          (record) =>
            record === null ||
            typeof record !== "object" ||
            Array.isArray(record)
        )
      ) {
        throw new Error("Catalog has an unexpected structure");
      }

      entries = records.map((record) => ({
        record,
        searchText: searchableText(record).toLowerCase(),
      }));
      entries.sort((left, right) => {
        const dateOrder = text(right.record.dateAdded).localeCompare(
          text(left.record.dateAdded)
        );
        return dateOrder || text(left.record.cveID).localeCompare(
          text(right.record.cveID)
        );
      });
      elements.catalogMeta.textContent =
        "Catalog version " + text(payload.catalogVersion) +
        " · Released " + text(payload.dateReleased).slice(0, 10) +
        " · " + entries.length.toLocaleString() + " entries";
      elements.fieldset.disabled = false;
      page = 1;
      applyFilters();
    } catch (_error) {
      entries = [];
      matches = [];
      elements.error.hidden = false;
      elements.results.hidden = true;
      elements.resultCount.textContent = "Catalog unavailable";
      elements.catalogMeta.textContent =
        "Catalog details are temporarily unavailable.";
    }
  }

  elements.form.addEventListener("input", () => {
    page = 1;
    applyFilters();
  });
  elements.form.addEventListener("change", () => {
    page = 1;
    applyFilters();
  });
  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    page = 1;
    applyFilters();
  });
  elements.form.addEventListener("reset", () => {
    window.setTimeout(() => {
      page = 1;
      applyFilters();
    }, 0);
  });
  elements.previous.addEventListener("click", () => {
    page -= 1;
    renderResults();
    elements.results.scrollIntoView({ block: "start" });
  });
  elements.next.addEventListener("click", () => {
    page += 1;
    renderResults();
    elements.results.scrollIntoView({ block: "start" });
  });
  elements.retry.addEventListener("click", loadCatalog);

  loadCatalog();
})();
