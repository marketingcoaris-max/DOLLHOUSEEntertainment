const header = document.querySelector("[data-header]");
const navToggle = document.querySelector("[data-nav-toggle]");
const mobileNav = document.querySelector("[data-mobile-nav]");
const revealTargets = Array.from(document.querySelectorAll(".reveal"));
const accordions = Array.from(document.querySelectorAll(".accordion"));
const sectionMores = Array.from(document.querySelectorAll("[data-more]"));

function setHeaderState() {
  if (!header) return;
  header.classList.toggle("is-scrolled", window.scrollY > 8);
}

function closeNavigation() {
  document.body.classList.remove("nav-open");
  mobileNav?.classList.remove("is-open");
  header?.classList.remove("is-open");
  navToggle?.setAttribute("aria-expanded", "false");
}

function scrollToHash(hash, behavior = "smooth") {
  if (!hash || hash === "#") return false;

  const target = document.querySelector(hash);
  if (!target) return false;

  const headerHeight = header?.offsetHeight || 0;
  const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 24;
  window.scrollTo({ top: Math.max(0, top), behavior });
  return true;
}

navToggle?.addEventListener("click", () => {
  const isOpen = !mobileNav?.classList.contains("is-open");
  document.body.classList.toggle("nav-open", isOpen);
  mobileNav?.classList.toggle("is-open", isOpen);
  header?.classList.toggle("is-open", isOpen);
  navToggle.setAttribute("aria-expanded", String(isOpen));
});

mobileNav?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", closeNavigation);
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const href = link.getAttribute("href");
    if (!href || href === "#") return;
    if (!scrollToHash(href)) return;

    event.preventDefault();
    history.pushState(null, "", href);
    closeNavigation();
  });
});

window.addEventListener("scroll", setHeaderState, { passive: true });
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeNavigation();
});

window.matchMedia("(min-width: 1181px)").addEventListener("change", (event) => {
  if (event.matches) closeNavigation();
});

setHeaderState();

window.addEventListener("load", () => {
  if (!window.location.hash) return;

  requestAnimationFrame(() => {
    scrollToHash(window.location.hash, "auto");
    window.setTimeout(() => scrollToHash(window.location.hash, "auto"), 250);
  });
});

window.addEventListener("hashchange", () => {
  scrollToHash(window.location.hash, "auto");
});

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { rootMargin: "0px 0px -10% 0px", threshold: 0.08 }
  );

  revealTargets.forEach((target) => revealObserver.observe(target));
} else {
  revealTargets.forEach((target) => target.classList.add("is-visible"));
}

accordions.forEach((accordion) => {
  const summary = accordion.querySelector("summary");
  const content = accordion.querySelector(".accordion-content");

  if (!summary || !content) return;

  summary.addEventListener("click", (event) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    event.preventDefault();
    if (accordion.dataset.animating === "true") return;

    const isOpen = accordion.open;
    const startHeight = accordion.offsetHeight;
    accordion.dataset.animating = "true";
    accordion.style.overflow = "hidden";
    accordion.style.height = `${startHeight}px`;

    if (!isOpen) {
      accordion.open = true;
    }

    const endHeight = isOpen ? summary.offsetHeight : summary.offsetHeight + content.offsetHeight;

    requestAnimationFrame(() => {
      accordion.style.transition = "height 300ms ease";
      accordion.style.height = `${endHeight}px`;
    });

    const finish = (transitionEvent) => {
      if (transitionEvent.target !== accordion || transitionEvent.propertyName !== "height") return;
      if (isOpen) accordion.open = false;
      accordion.style.height = "";
      accordion.style.overflow = "";
      accordion.style.transition = "";
      delete accordion.dataset.animating;
      accordion.removeEventListener("transitionend", finish);
    };

    accordion.addEventListener("transitionend", finish);
  });
});

sectionMores.forEach((item) => {
  const summary = item.querySelector("summary");
  const content = item.querySelector(".section-more-content");
  const label = summary?.querySelector(".more-label");

  if (!summary || !content) return;

  const openLabel = summary.dataset.openLabel || label?.textContent || "詳細を見る";
  const closeLabel = summary.dataset.closeLabel || "閉じる";

  function updateMoreState() {
    const text = item.open ? closeLabel : openLabel;
    if (label) label.textContent = text;
    summary.setAttribute("aria-expanded", String(item.open));
    summary.setAttribute("aria-label", text);
  }

  updateMoreState();
  item.addEventListener("toggle", updateMoreState);

  summary.addEventListener("click", (event) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    event.preventDefault();
    if (item.dataset.animating === "true") return;

    const isOpen = item.open;
    const startHeight = item.offsetHeight;
    item.dataset.animating = "true";
    item.style.overflow = "hidden";
    item.style.height = `${startHeight}px`;

    if (!isOpen) {
      item.open = true;
    }

    const endHeight = isOpen ? summary.offsetHeight : summary.offsetHeight + content.offsetHeight;

    requestAnimationFrame(() => {
      item.style.transition = "height 300ms ease";
      item.style.height = `${endHeight}px`;
    });

    const finish = (transitionEvent) => {
      if (transitionEvent.target !== item || transitionEvent.propertyName !== "height") return;
      if (isOpen) item.open = false;
      item.style.height = "";
      item.style.overflow = "";
      item.style.transition = "";
      delete item.dataset.animating;
      item.removeEventListener("transitionend", finish);
    };

    item.addEventListener("transitionend", finish);
  });
});
