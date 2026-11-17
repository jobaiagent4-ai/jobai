const ICONS = {
  pin: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>',
  building: '<svg class="icon icon-sm" viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M8 10h.01M16 10h.01M12 10h.01M8 14h.01M16 14h.01M12 14h.01"/></svg>',
  briefcase: '<svg class="icon icon-sm" viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>',
  clock: '<svg class="icon icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
  phone: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.96.36 1.9.7 2.79a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.89.34 1.83.58 2.79.7A2 2 0 0 1 22 16.92Z"/></svg>',
  link: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>',
};

const newJobsBtn = document.getElementById("newJobsBtn");
const shopsBtn = document.getElementById("shopsBtn");
const fetchShopsBtn = document.getElementById("fetchShopsBtn");
const message = document.getElementById("message");
const results = document.getElementById("results");
const shopsView = document.getElementById("shopsView");
const shopsStatus = document.getElementById("shopsStatus");
const shopsExcelBtn = document.getElementById("shopsExcelBtn");
let activeView = "jobs";

// Escape text so job data can never inject HTML
function esc(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function formatDate(value) {
  if (!value) return "Date not available";
  const d = new Date(value);
  if (isNaN(d)) return "Date not available";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function formatType(value) {
  if (!value) return "Not specified";
  return value.replace(/_/g, " ").toLowerCase().replace(/^\w/, c => c.toUpperCase());
}

function safeUrl(url) {
  return typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;
}

function safePhoneUrl(phone) {
  const number = String(phone ?? "").trim().replace(/[\s().-]/g, "");
  return /^\+?\d{5,15}$/.test(number) ? "tel:" + number : null;
}

function createCard(job) {
  const isKerala = job.region === "Kerala";
  const location = [job.city, job.state].filter(Boolean).join(", ") || "Location not specified";
  const link = safeUrl(job.apply_link);
  const contact = job.contact == null ? "" : String(job.contact).trim();
  const contactLink = safePhoneUrl(contact);
  const region = isKerala ? "Kerala" : "Across India";

  const card = document.createElement("article");
  card.className = "card " + (isKerala ? "kerala" : "outside");
  card.innerHTML = `
    <div class="card-top">
      <span class="card-kicker">OPEN ROLE</span>
      <span class="region-pill">${region}</span>
    </div>
    <h3 class="card-title">${esc(job.title) || "Untitled role"}</h3>
    <div class="meta">
      <div class="meta-row">${ICONS.building}<span>${esc(job.company) || "Company not listed"}</span></div>
      <div class="meta-row">${ICONS.pin}<span>${esc(location)}</span></div>
      <div class="meta-row">${ICONS.briefcase}<span>${esc(formatType(job.type))}</span></div>
      <div class="meta-row">${ICONS.clock}<span>${esc(formatDate(job.posted))}</span></div>
      ${contact ? `<div class="meta-row">${ICONS.phone}<span>${contactLink ? `<a class="phone-link" href="${contactLink}">${esc(contact)}</a>` : esc(contact)}</span></div>` : ""}
    </div>
    <div class="card-foot">
      ${link ? `<a class="apply" href="${esc(link)}" target="_blank" rel="noopener noreferrer">Apply ${ICONS.link}</a>` : ""}
    </div>
  `;
  return card;
}

function fillGrid(gridId, countId, jobs) {
  const grid = document.getElementById(gridId);
  grid.innerHTML = "";
  document.getElementById(countId).textContent = jobs.length + (jobs.length === 1 ? " job" : " jobs");

  if (jobs.length === 0) {
    grid.innerHTML = '<p class="empty-note">No jobs found.</p>';
    return;
  }
  jobs.forEach(job => grid.appendChild(createCard(job)));
}

function uniqueJobsByTitle(jobs) {
  const seenJobs = new Set();
  return jobs.filter(job => {
    const title = job.title;
    const company = job.company;
    if (typeof title !== "string" || !title || typeof company !== "string" || !company) return true;

    const key = JSON.stringify([title, company]);
    if (seenJobs.has(key)) return false;
    seenJobs.add(key);
    return true;
  });
}

function showMessage(html, isError = false) {
  results.hidden = true;
  shopsView.hidden = true;
  message.hidden = false;
  message.className = "empty-state" + (isError ? " error" : "");
  message.innerHTML = html;
}

async function loadJobs() {
  activeView = "jobs";
  newJobsBtn.classList.add("active");
  shopsBtn.classList.remove("active");
  message.hidden = true;
  shopsView.hidden = true;
  results.hidden = true;

  try {
    const response = await fetch("/jobs");
    if (!response.ok) throw new Error(await response.text());

    const jobs = await response.json();
    if (activeView !== "jobs") return;
    jobs.sort((a, b) => new Date(b.posted || 0) - new Date(a.posted || 0));
    const uniqueJobs = uniqueJobsByTitle(jobs);

    fillGrid("keralaGrid", "keralaCount", uniqueJobs.filter(j => j.region === "Kerala"));
    fillGrid("outsideGrid", "outsideCount", uniqueJobs.filter(j => j.region !== "Kerala"));

    message.hidden = true;
    results.hidden = false;
  } catch (err) {
    if (activeView === "jobs") {
      showMessage("<p>" + esc(err.message || "Could not load jobs.") + "</p>", true);
    }
  }
}

function fillShopGroup(gridId, countId, shops, regionLabel) {
  const grid = document.getElementById(gridId);
  grid.innerHTML = "";
  document.getElementById(countId).textContent =
    shops.length + (shops.length === 1 ? " shop" : " shops");

  if (shops.length === 0) {
    grid.innerHTML =
      '<p class="shop-empty">No ' + regionLabel + ' shops found yet.</p>';
    return;
  }

  shops.forEach(shop => {
    const contactLink = safePhoneUrl(shop.contact);
    const card = document.createElement("article");
    card.className = "shop-card";
    card.innerHTML = `
      <div class="shop-card-heading">
        <h3>${esc(shop.name) || "Unnamed shop"}</h3>
        <span class="shop-region ${shop.region === "Kerala" ? "kerala" : "outside"}">${regionLabel}</span>
      </div>
      <div class="meta">
        <div class="meta-row">${ICONS.pin}<span>${esc(shop.location) || "Location not available"}</span></div>
        <div class="meta-row">${ICONS.phone}<span>${contactLink ? `<a class="phone-link" href="${contactLink}">${esc(shop.contact)}</a>` : esc(shop.contact) || "Contact not available"}</span></div>
        ${shop.category ? `<div class="meta-row">${ICONS.building}<span>${esc(shop.category)}</span></div>` : ""}
      </div>
    `;
    grid.appendChild(card);
  });
}

function fillShops(shops) {
  fillShopGroup(
    "keralaShopsGrid",
    "keralaShopsCount",
    shops.filter(shop => shop.region === "Kerala"),
    "Kerala"
  );
  fillShopGroup(
    "outsideShopsGrid",
    "outsideShopsCount",
    shops.filter(shop => shop.region !== "Kerala"),
    "outside Kerala"
  );
}

async function loadShops() {
  activeView = "shops";
  newJobsBtn.classList.remove("active");
  shopsBtn.classList.add("active");
  message.hidden = true;
  results.hidden = true;
  shopsView.hidden = false;
  fetchShopsBtn.hidden = true;
  shopsExcelBtn.hidden = true;
  shopsStatus.textContent = "Loading saved shops...";

  try {
    const response = await fetch("/shops");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load shops.");
    if (activeView !== "shops") return;
    fillShops(data);
    shopsStatus.textContent = data.length + (data.length === 1 ? " shop saved" : " shops saved");
    fetchShopsBtn.hidden = false;
    shopsExcelBtn.hidden = false;
  } catch (err) {
    if (activeView !== "shops") return;
    shopsStatus.textContent = "";
    showMessage("<p>" + esc(err.message || "Could not load shops.") + "</p>", true);
  }
}

async function fetchShops() {
  fetchShopsBtn.disabled = true;
  shopsStatus.textContent = "Searching for mobile and laptop shops across India...";
  try {
    const response = await fetch("/shops/fetch", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not fetch shops.");
    fillShops(data);
    shopsStatus.textContent = data.length + (data.length === 1 ? " shop saved" : " shops saved");
  } catch (err) {
    shopsStatus.textContent = err.message || "Could not fetch shops.";
  } finally {
    fetchShopsBtn.disabled = false;
  }
}

newJobsBtn.addEventListener("click", loadJobs);
shopsBtn.addEventListener("click", loadShops);
fetchShopsBtn.addEventListener("click", fetchShops);
loadJobs();