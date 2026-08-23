(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const aboutBackground = new URLSearchParams(window.location.search).get("about-bg");
  if (aboutBackground === "city") document.documentElement.dataset.aboutBg = "city";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const desktopQuery = window.matchMedia("(min-width: 768px)");
  const header = document.querySelector("[data-header]");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const mobileNav = document.querySelector("[data-mobile-nav]");
  const pageScroll = document.querySelector("[data-page-scroll]");

  const setNavOpen = (open, returnFocus = false) => {
    if (!navToggle || !mobileNav) return;
    if (!open && (returnFocus || mobileNav.contains(document.activeElement))) {
      const focusTarget = desktopQuery.matches ? header?.querySelector(".brand") : navToggle;
      focusTarget?.focus();
    }
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "メニューを閉じる" : "メニューを開く");
    mobileNav.setAttribute("aria-hidden", String(!open));
    mobileNav.classList.toggle("is-open", open);
    mobileNav.inert = !open;
    document.body.classList.toggle("nav-open", open);
  };

  navToggle?.addEventListener("click", () => {
    setNavOpen(navToggle.getAttribute("aria-expanded") !== "true");
  });

  mobileNav?.querySelectorAll("a[href]").forEach((link) => {
    link.addEventListener("click", () => setNavOpen(false));
  });

  document.addEventListener("keydown", (event) => {
    if (!navToggle || !mobileNav || navToggle.getAttribute("aria-expanded") !== "true") return;
    if (event.key === "Escape") {
      event.preventDefault();
      setNavOpen(false, true);
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [navToggle, ...mobileNav.querySelectorAll("a[href]")];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  let responsiveScrollProgress = 0;
  let transferringScrollPosition = false;
  const rememberScrollPosition = () => {
    if (transferringScrollPosition) return;
    const scroller = desktopQuery.matches ? document.scrollingElement : pageScroll;
    if (!scroller) return;
    const maximum = Math.max(scroller.scrollHeight - scroller.clientHeight, 0);
    responsiveScrollProgress = maximum ? scroller.scrollTop / maximum : 0;
  };

  window.addEventListener("scroll", rememberScrollPosition, { passive: true });
  pageScroll?.addEventListener("scroll", rememberScrollPosition, { passive: true });

  desktopQuery.addEventListener("change", (event) => {
    if (event.matches) setNavOpen(false);
    transferringScrollPosition = true;
    window.requestAnimationFrame(() => {
      const scroller = event.matches ? document.scrollingElement : pageScroll;
      if (scroller) {
        const maximum = Math.max(scroller.scrollHeight - scroller.clientHeight, 0);
        scroller.scrollTop = responsiveScrollProgress * maximum;
      }
      window.requestAnimationFrame(() => {
        transferringScrollPosition = false;
        rememberScrollPosition();
      });
    });
  });

  rememberScrollPosition();

  setNavOpen(false);

  document.addEventListener("keydown", (event) => {
    if (desktopQuery.matches || !pageScroll || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    const active = document.activeElement;
    if (active?.matches("input, select, textarea, button, summary, [contenteditable='true']")) return;

    const pageStep = Math.max(pageScroll.clientHeight - 64, 160);
    const keySteps = {
      ArrowDown: 48,
      ArrowUp: -48,
      PageDown: pageStep,
      PageUp: -pageStep,
      " ": event.shiftKey ? -pageStep : pageStep
    };

    if (event.key === "Home") {
      event.preventDefault();
      pageScroll.scrollTo({ top: 0, behavior: "auto" });
    } else if (event.key === "End") {
      event.preventDefault();
      pageScroll.scrollTo({ top: pageScroll.scrollHeight, behavior: "auto" });
    } else if (Object.prototype.hasOwnProperty.call(keySteps, event.key)) {
      event.preventDefault();
      pageScroll.scrollBy({ top: keySteps[event.key], behavior: "auto" });
    }
  });

  const contactForm = document.querySelector("[data-contact-form]");
  const purposeField = document.querySelector("[data-purpose-field]");
  const messageField = document.querySelector("[data-message-field]");
  const annualSalesField = document.querySelector("[data-sales-field]");
  const selectedContext = document.querySelector("[data-selected-context]");
  const formStatus = document.querySelector("[data-form-status]");
  const formFrame = document.querySelector("[data-form-frame]");
  const contactTarget = document.querySelector("#contact-form");
  const submitButton = contactForm?.querySelector("[type='submit']");
  let formSubmitted = false;

  const escapeName = (name) => (
    window.CSS?.escape ? window.CSS.escape(name) : name.replace(/[.]/g, "\\.")
  );

  const addUniqueLine = (field, line) => {
    if (!field || !line) return;
    const lines = field.value.split("\n").filter(Boolean);
    if (lines.includes(line)) return;
    field.value = [line, ...lines].join("\n");
  };

  const selectPurposeByIntent = (select, intent) => {
    if (!select) return false;
    const option = Array.from(select.options).find((item) => (
      item.dataset.intent === intent || item.textContent.trim() === intent
    ));
    if (!option) return false;
    select.selectedIndex = option.index;
    return true;
  };

  const clearFieldError = (field) => {
    field.removeAttribute("aria-invalid");
    const error = contactForm?.querySelector(`[data-error-for="${escapeName(field.name)}"]`);
    if (error) error.textContent = "";
  };

  const applyConsultTopic = (kind, topic) => {
    if (!topic) return;
    const isIssue = kind === "issue";
    const purpose = isIssue ? "組織課題の整理相談（社長依存・幹部育成など）" : topic;

    if (purposeField) {
      if (!selectPurposeByIntent(purposeField, purpose)) selectPurposeByIntent(purposeField, "その他");
      clearFieldError(purposeField);
    }

    addUniqueLine(messageField, `${isIssue ? "【ご相談課題】" : "【ご相談希望】"}${topic}`);

    if (selectedContext) {
      selectedContext.hidden = false;
      selectedContext.textContent = `${isIssue ? "選択中の経営課題" : "選択中の相談内容"}：${topic}`;
    }

    contactTarget?.scrollIntoView({
      behavior: reducedMotion.matches ? "auto" : "smooth",
      block: "start"
    });

    window.setTimeout(() => purposeField?.focus({ preventScroll: true }), reducedMotion.matches ? 0 : 480);
  };

  document.querySelectorAll("[data-consult-topic]").forEach((control) => {
    control.addEventListener("click", () => {
      applyConsultTopic(control.dataset.consultKind || "program", control.dataset.consultTopic || "");
    });
  });

  purposeField?.addEventListener("change", () => {
    const option = purposeField.selectedOptions[0];
    const intent = option?.dataset.intent || option?.textContent.trim();
    if (!selectedContext || !intent || !purposeField.value) return;
    selectedContext.hidden = false;
    selectedContext.textContent = `選択中の相談内容：${intent}`;
  });

  const errorMessages = {
    "entry.1923578332": "お問い合わせ目的を選択してください。",
    "entry.817700229": "お名前を入力してください。",
    "entry.1292858443": "会社名・団体名を入力してください。",
    "entry.825599773": "有効なメールアドレスを入力してください。",
    "entry.43293874": "電話番号を入力してください。",
    "entry.918018694": "相談内容を入力してください。",
    "entry.236822912": "個人情報の取り扱いへの同意が必要です。"
  };

  const showFieldError = (field) => {
    field.setAttribute("aria-invalid", "true");
    const error = contactForm?.querySelector(`[data-error-for="${escapeName(field.name)}"]`);
    if (error) error.textContent = errorMessages[field.name] || "入力内容をご確認ください。";
  };

  const requiredFields = contactForm ? Array.from(contactForm.querySelectorAll("[required]")) : [];

  requiredFields.forEach((field) => {
    const eventName = field.matches("select, input[type='checkbox']") ? "change" : "input";
    field.addEventListener(eventName, () => {
      if (field.checkValidity()) clearFieldError(field);
    });
  });

  const validateForm = () => {
    let firstInvalid = null;
    requiredFields.forEach((field) => {
      if (field.checkValidity()) clearFieldError(field);
      else {
        showFieldError(field);
        if (!firstInvalid) firstInvalid = field;
      }
    });
    if (!firstInvalid) return true;
    firstInvalid.focus();
    firstInvalid.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block: "center" });
    if (formStatus) formStatus.textContent = "未入力または入力形式に誤りがある項目をご確認ください。";
    return false;
  };

  contactForm?.addEventListener("submit", (event) => {
    if (!validateForm()) {
      event.preventDefault();
      return;
    }

    const selectedPurpose = purposeField?.selectedOptions[0];
    const purposeIntent = selectedPurpose?.dataset.intent || selectedPurpose?.textContent.trim();
    if (purposeIntent) {
      const prefix = purposeIntent.startsWith("組織課題") ? "【ご相談課題】" : "【ご相談希望】";
      const hasSpecificIssue = prefix === "【ご相談課題】" && messageField?.value
        .split("\n")
        .some((line) => line.startsWith(prefix));
      if (!hasSpecificIssue) addUniqueLine(messageField, `${prefix}${purposeIntent}`);
    }

    if (annualSalesField?.value && messageField) {
      const prefix = "【年商規模】";
      const lines = messageField.value.split("\n").filter((line) => !line.startsWith(prefix));
      messageField.value = [`${prefix}${annualSalesField.value}`, ...lines].join("\n").trim();
    }

    formSubmitted = true;
    if (submitButton) submitButton.disabled = true;
    if (formStatus) formStatus.textContent = "送信しています。画面を閉じずにお待ちください。";
  });

  formFrame?.addEventListener("load", () => {
    if (!formSubmitted) return;
    if (formStatus) formStatus.textContent = "送信が完了しました。内容を確認のうえ、担当者よりご連絡します。";
    contactForm?.reset();
    requiredFields.forEach(clearFieldError);
    if (submitButton) submitButton.disabled = false;
    if (selectedContext) selectedContext.hidden = true;
    formSubmitted = false;
  });

  const counters = document.querySelectorAll("[data-count-to]");
  const formatNumber = (value) => new Intl.NumberFormat("ja-JP").format(value);
  const animateCounter = (counter) => {
    if (counter.dataset.counted === "true") return;
    counter.dataset.counted = "true";
    const target = Number(counter.dataset.countTo || "0");
    if (!Number.isFinite(target) || reducedMotion.matches) {
      counter.textContent = formatNumber(target);
      return;
    }
    const start = performance.now();
    const duration = 1000;
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      counter.textContent = formatNumber(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  if ("IntersectionObserver" in window) {
    const counterObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      });
    }, { threshold: .45 });
    counters.forEach((counter) => {
      counter.textContent = "0";
      counterObserver.observe(counter);
    });
  } else {
    counters.forEach(animateCounter);
  }

  const labIndex = document.querySelector("[data-lab-index]");
  if (labIndex && "IntersectionObserver" in window) {
    const links = Array.from(labIndex.querySelectorAll("a[href^='#']"));
    const sections = links.map((link) => document.querySelector(link.getAttribute("href"))).filter(Boolean);
    const visible = new Map();
    const setCurrent = () => {
      const candidates = sections.filter((section) => visible.get(section));
      const current = candidates[0];
      links.forEach((link) => {
        if (current && link.getAttribute("href") === `#${current.id}`) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => visible.set(entry.target, entry.isIntersecting));
      setCurrent();
    }, { rootMargin: "-30% 0px -55%", threshold: 0 });
    sections.forEach((section) => observer.observe(section));
  }

  const openHashDetails = () => {
    if (!window.location.hash) return;
    const target = document.querySelector(window.location.hash);
    const details = target?.matches("details") ? target : target?.closest("details");
    if (details) details.open = true;
  };
  window.addEventListener("hashchange", openHashDetails);
  openHashDetails();

  const instagramFeed = document.querySelector("[data-instagram-feed]");
  const instagramProfile = "https://www.instagram.com/shainkyouikulab.2000/";
  const setupInstagramTrack = (track) => {
    if (!track || track.dataset.keyboardReady === "true") return;
    track.dataset.keyboardReady = "true";
    track.addEventListener("keydown", (event) => {
      if (!event.key.startsWith("Arrow")) return;
      event.preventDefault();
      track.scrollBy({ left: event.key === "ArrowRight" ? 280 : -280, behavior: reducedMotion.matches ? "auto" : "smooth" });
    });
  };

  const createInstagramMoreCard = () => {
    const item = document.createElement("li");
    item.className = "instagram-more";
    const link = document.createElement("a");
    link.href = instagramProfile;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.append(document.createTextNode("Instagramを"), document.createElement("br"), document.createTextNode("もっと見る "));
    const arrow = document.createElement("span");
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    link.append(arrow);
    item.append(link);
    return item;
  };
  const safeHttpUrl = (value) => {
    try {
      const url = new URL(String(value || ""), window.location.href);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
      return "";
    }
  };

  const renderInstagramFallback = () => {
    if (!instagramFeed) return;
    instagramFeed.replaceChildren();
    const fallback = document.createElement("div");
    fallback.className = "instagram-fallback";
    const text = document.createElement("p");
    text.textContent = "最新投稿を取得できませんでした。公式プロフィールからご覧ください。";
    const link = document.createElement("a");
    link.className = "button button-outline";
    link.href = instagramProfile;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Instagramを見る";
    fallback.append(text, link);
    instagramFeed.append(fallback);
  };

  const renderInstagramPosts = (posts) => {
    if (!instagramFeed) return;
    const track = document.createElement("ul");
    track.className = "instagram-track";
    track.tabIndex = 0;
    track.setAttribute("aria-label", "Instagramの最新投稿。横にスクロールして閲覧できます。");
    posts.forEach((post) => {
      const mediaUrl = post.safeMediaUrl;
      const permalink = post.safePermalink;
      if (!mediaUrl || !permalink) return;

      const item = document.createElement("li");
      const card = document.createElement("a");
      card.className = "instagram-card";
      card.href = permalink;
      card.target = "_blank";
      card.rel = "noopener noreferrer";

      const media = document.createElement("span");
      media.className = "instagram-card-media";
      const image = document.createElement("img");
      image.src = mediaUrl;
      const caption = String(post.caption || "").trim();
      image.alt = caption ? caption.slice(0, 80) : "社員教育Lab. Instagram投稿";
      image.loading = "lazy";
      image.decoding = "async";
      image.width = 720;
      image.height = 720;
      media.append(image);

      const body = document.createElement("span");
      body.className = "instagram-card-copy";
      const timestamp = new Date(post.timestamp);
      const date = Number.isNaN(timestamp.getTime())
        ? "Instagramで投稿を見る"
        : new Intl.DateTimeFormat("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit" }).format(timestamp);
      const shortCaption = caption.length > 96 ? `${caption.slice(0, 96)}…` : caption;
      body.textContent = `${date}　${shortCaption || "Instagramで投稿を見る"}`;
      card.append(media, body);
      item.append(card);
      track.append(item);
    });
    if (!track.children.length) {
      renderInstagramFallback();
      return;
    }
    track.append(createInstagramMoreCard());
    instagramFeed.replaceChildren(track);
    setupInstagramTrack(track);
  };

  const loadInstagram = async () => {
    if (!instagramFeed) return;
    const endpoint = instagramFeed.dataset.instagramEndpoint?.trim();
    if (!endpoint) return;

    let endpointUrl;
    try {
      endpointUrl = new URL(endpoint, window.location.href);
    } catch {
      renderInstagramFallback();
      return;
    }
    if (endpointUrl.origin !== window.location.origin) {
      renderInstagramFallback();
      return;
    }

    try {
      const response = await fetch(endpointUrl, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Instagram feed unavailable");
      const payload = await response.json();
      const source = Array.isArray(payload) ? payload : payload.posts;
      if (!Array.isArray(source)) throw new Error("Instagram feed invalid");
      const latest = source
        .map((post) => {
          const mediaType = String(post.media_type || "").toUpperCase();
          const rawMediaUrl = mediaType === "VIDEO" ? post.thumbnail_url || post.media_url : post.media_url;
          return {
            ...post,
            mediaType,
            safeMediaUrl: safeHttpUrl(rawMediaUrl),
            safePermalink: safeHttpUrl(post.permalink)
          };
        })
        .filter((post) => (
          ["IMAGE", "CAROUSEL_ALBUM", "VIDEO"].includes(post.mediaType)
          && post.safeMediaUrl
          && post.safePermalink
        ))
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 3);
      if (!latest.length) throw new Error("Instagram feed empty");
      renderInstagramPosts(latest);
    } catch {
      renderInstagramFallback();
    }
  };

  setupInstagramTrack(instagramFeed?.querySelector("[data-instagram-track]"));
  loadInstagram();
})();
