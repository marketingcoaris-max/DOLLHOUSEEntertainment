const header = document.querySelector("[data-header]");
const navToggle = document.querySelector("[data-nav-toggle]");
const mobileNav = document.querySelector("[data-mobile-nav]");
const loadingScreen = document.querySelector("[data-loading-screen]");
const revealTargets = Array.from(document.querySelectorAll(".reveal"));
const countTargets = Array.from(document.querySelectorAll("[data-count-target]"));
const sectionMores = Array.from(document.querySelectorAll("[data-more]"));
const crossfadeGroups = Array.from(document.querySelectorAll("[data-crossfade]"));
const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const inPageNavLinks = Array.from(
  document.querySelectorAll('.site-nav a[href^="#"], .mobile-nav a[href^="#"]')
);
const trackedHashes = new Set(inPageNavLinks.map((link) => link.getAttribute("href")));
const trackedSections = Array.from(document.querySelectorAll("main section[id]")).filter((section) =>
  trackedHashes.has("#" + section.id)
);
const countAnimationFrames = new Map();

function addMediaQueryListener(query, listener) {
  if (typeof query.addEventListener === "function") {
    query.addEventListener("change", listener);
  } else if (typeof query.addListener === "function") {
    query.addListener(listener);
  }
}

function updatePagePosition() {
  const root = document.documentElement;
  const scrollable = Math.max(root.scrollHeight - window.innerHeight, 1);
  const progress = Math.min(Math.max(window.scrollY / scrollable, 0), 1);
  const marker = window.scrollY + (header?.offsetHeight || 0) + window.innerHeight * 0.22;
  let activeId = "";

  root.style.setProperty("--page-progress", progress * 100 + "%");

  trackedSections.forEach((section) => {
    if (section.offsetTop <= marker) activeId = section.id;
  });

  inPageNavLinks.forEach((link) => {
    const isCurrent = link.getAttribute("href") === "#" + activeId;
    link.classList.toggle("is-current", isCurrent);
    if (isCurrent) {
      link.setAttribute("aria-current", "location");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function setHeaderState() {
  header?.classList.toggle("is-scrolled", window.scrollY > 8);
  updatePagePosition();
}

function setNavigationState(isOpen, restoreFocus = false) {
  document.body.classList.toggle("nav-open", isOpen);
  mobileNav?.classList.toggle("is-open", isOpen);
  header?.classList.toggle("is-open", isOpen);
  navToggle?.setAttribute("aria-expanded", String(isOpen));
  mobileNav?.setAttribute("aria-hidden", String(!isOpen));

  if (mobileNav) {
    mobileNav.inert = !isOpen;
  }

  if (!isOpen && restoreFocus) {
    navToggle?.focus();
  }
}

function scrollToHash(hash, behavior = "smooth") {
  if (!hash || hash === "#") return false;

  let target;
  try {
    target = document.querySelector(hash);
  } catch {
    return false;
  }

  if (!target) return false;

  const headerHeight = header?.offsetHeight || 0;
  const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 24;
  window.scrollTo({
    top: Math.max(0, top),
    behavior: reducedMotionQuery.matches ? "auto" : behavior
  });
  return true;
}

function formatCount(value, suffix) {
  return Math.round(value).toLocaleString("ja-JP") + (suffix || "");
}

function finishCount(target) {
  const frame = countAnimationFrames.get(target);
  if (frame) cancelAnimationFrame(frame);
  countAnimationFrames.delete(target);

  const endValue = Number(target?.dataset.countTarget || 0);
  const suffix = target?.dataset.countSuffix || "";
  if (target && Number.isFinite(endValue)) {
    target.textContent = formatCount(endValue, suffix);
    target.dataset.counted = "true";
  }
}

function animateCount(target) {
  if (!target || target.dataset.counted === "true") return;

  const endValue = Number(target.dataset.countTarget || 0);
  const suffix = target.dataset.countSuffix || "";
  target.dataset.counted = "true";

  if (!Number.isFinite(endValue) || reducedMotionQuery.matches) {
    finishCount(target);
    return;
  }

  const duration = 1600;
  const startTime = performance.now();

  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    target.textContent = formatCount(Math.max(1, endValue * eased), suffix);

    if (progress < 1) {
      countAnimationFrames.set(target, requestAnimationFrame(tick));
    } else {
      finishCount(target);
    }
  }

  target.textContent = formatCount(1, suffix);
  countAnimationFrames.set(target, requestAnimationFrame(tick));
}

function setupCrossfade(group) {
  const slides = Array.from(group.querySelectorAll("img"));
  if (slides.length < 2) return;

  const interval = Math.max(Number(group.dataset.interval) || 10000, 3000);
  let activeIndex = Math.max(slides.findIndex((slide) => slide.classList.contains("is-active")), 0);
  let timer = null;

  const showSlide = (index) => {
    activeIndex = index;
    slides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === activeIndex;
      slide.classList.toggle("is-active", isActive);
      slide.setAttribute("aria-hidden", String(!isActive));
    });
  };

  const stop = () => {
    if (timer === null) return;
    window.clearInterval(timer);
    timer = null;
  };

  const start = () => {
    stop();

    if (reducedMotionQuery.matches) {
      showSlide(0);
      return;
    }

    showSlide(activeIndex);
    if (document.hidden) return;

    timer = window.setInterval(() => {
      showSlide((activeIndex + 1) % slides.length);
    }, interval);
  };

  document.addEventListener("visibilitychange", start);
  addMediaQueryListener(reducedMotionQuery, start);
  start();
}

function finishSplash() {
  if (!loadingScreen || !loadingScreen.isConnected) {
    document.documentElement.classList.remove("has-splash", "is-splash-hiding");
    return;
  }

  let removed = false;
  const removeSplash = () => {
    if (removed) return;
    removed = true;
    loadingScreen.remove();
    document.documentElement.classList.remove("has-splash", "is-splash-hiding");
    document.documentElement.classList.add("splash-complete");
  };

  if (reducedMotionQuery.matches) {
    removeSplash();
    return;
  }

  document.documentElement.classList.add("is-splash-hiding");
  loadingScreen.addEventListener(
    "transitionend",
    (event) => {
      if (event.target === loadingScreen && event.propertyName === "opacity") {
        removeSplash();
      }
    },
    { once: true }
  );
  window.setTimeout(removeSplash, 900);
}

revealTargets.forEach((target, index) => {
  target.style.setProperty("--reveal-delay", Math.min((index % 6) * 70, 280) + "ms");
});

crossfadeGroups.forEach(setupCrossfade);
setNavigationState(false);
setHeaderState();

navToggle?.addEventListener("click", () => {
  setNavigationState(!mobileNav?.classList.contains("is-open"));
});

document.querySelectorAll('a[href^="#"]:not(.skip-link)').forEach((link) => {
  link.addEventListener("click", (event) => {
    const href = link.getAttribute("href");
    if (!href || href === "#" || !scrollToHash(href)) return;

    event.preventDefault();
    history.pushState(null, "", href);
    setNavigationState(false);
  });
});

window.addEventListener("scroll", setHeaderState, { passive: true });
window.addEventListener("resize", setHeaderState, { passive: true });
window.addEventListener("pageshow", setHeaderState);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && mobileNav?.classList.contains("is-open")) {
    setNavigationState(false, true);
  }
});

addMediaQueryListener(window.matchMedia("(min-width: 1181px)"), (event) => {
  if (event.matches) setNavigationState(false);
});

window.addEventListener("load", () => {
  window.setTimeout(finishSplash, reducedMotionQuery.matches ? 0 : 650);
  updatePagePosition();

  if (!window.location.hash) return;
  requestAnimationFrame(() => {
    scrollToHash(window.location.hash, "auto");
    window.setTimeout(() => scrollToHash(window.location.hash, "auto"), 250);
  });
});

if (document.readyState === "complete") {
  window.setTimeout(finishSplash, reducedMotionQuery.matches ? 0 : 650);
}
window.setTimeout(finishSplash, reducedMotionQuery.matches ? 0 : 3200);

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
    { rootMargin: "0px 0px -8% 0px", threshold: 0.06 }
  );

  revealTargets.forEach((target) => revealObserver.observe(target));

  const countObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animateCount(entry.target);
        countObserver.unobserve(entry.target);
      });
    },
    { rootMargin: "0px 0px -8% 0px", threshold: 0.3 }
  );

  countTargets.forEach((target) => countObserver.observe(target));
} else {
  revealTargets.forEach((target) => target.classList.add("is-visible"));
  countTargets.forEach(animateCount);
}

addMediaQueryListener(reducedMotionQuery, (event) => {
  if (!event.matches) return;
  revealTargets.forEach((target) => target.classList.add("is-visible"));
  countTargets.forEach(finishCount);
  finishSplash();
});

sectionMores.forEach((item) => {
  const summary = item.querySelector("summary");
  const content = item.querySelector(".section-more-content");
  if (!summary || !content) return;

  summary.setAttribute("aria-expanded", String(item.open));
  item.addEventListener("toggle", () => {
    summary.setAttribute("aria-expanded", String(item.open));
  });

  summary.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    summary.click();
  });

  summary.addEventListener("click", (event) => {
    if (reducedMotionQuery.matches) return;

    event.preventDefault();
    if (item.dataset.animating === "true") return;

    const isOpen = item.open;
    const startHeight = item.offsetHeight;
    item.dataset.animating = "true";
    item.style.overflow = "hidden";
    item.style.height = startHeight + "px";

    if (!isOpen) item.open = true;
    const endHeight = isOpen ? summary.offsetHeight : item.scrollHeight;

    requestAnimationFrame(() => {
      item.style.transition = "height 300ms ease";
      item.style.height = endHeight + "px";
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
