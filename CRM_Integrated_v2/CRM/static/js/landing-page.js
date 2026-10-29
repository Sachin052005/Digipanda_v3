/**
 * TECHPANDA CRM - Landing Page Interaction Module
 * Lightweight vanilla JavaScript (Zero external dependencies)
 * Handles: Mobile Navigation, Feature Showcase Tabs, WhatsApp Simulator,
 * Admissions Growth Calculator, and FAQ Accordions.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initMobileNav();
    initShowcaseTabs();
    initWhatsAppSimulator();
    initAdmissionsCalculator();
    initFaqAccordion();
  });

  // ==========================================================================
  // 1. MOBILE NAVIGATION
  // ==========================================================================
  function initMobileNav() {
    var menuBtn = document.getElementById('lpMobileMenuBtn');
    var nav = document.getElementById('lpNav');
    if (!menuBtn || !nav) return;

    menuBtn.addEventListener('click', function () {
      var isExpanded = menuBtn.getAttribute('aria-expanded') === 'true';
      menuBtn.setAttribute('aria-expanded', !isExpanded);
      nav.classList.toggle('is-open');
    });

    // Close when clicking a link
    nav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        menuBtn.setAttribute('aria-expanded', 'false');
        nav.classList.remove('is-open');
      });
    });
  }

  // ==========================================================================
  // 2. INTERACTIVE FEATURE SHOWCASE TABS
  // ==========================================================================
  function initShowcaseTabs() {
    var tabBtns = document.querySelectorAll('.lp-tab-btn');
    var tabPanes = document.querySelectorAll('.lp-tab-pane');
    if (tabBtns.length === 0 || tabPanes.length === 0) return;

    tabBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var targetId = btn.getAttribute('data-tab-target');
        if (!targetId) return;

        tabBtns.forEach(function (b) {
          b.classList.remove('is-active');
          b.setAttribute('aria-selected', 'false');
        });
        tabPanes.forEach(function (p) {
          p.classList.remove('is-active');
        });

        btn.classList.add('is-active');
        btn.setAttribute('aria-selected', 'true');
        var targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add('is-active');
      });

      // Keyboard arrow navigation
      btn.addEventListener('keydown', function (e) {
        var btnArray = Array.from(tabBtns);
        var idx = btnArray.indexOf(btn);
        if (e.key === 'ArrowRight') {
          var next = btnArray[(idx + 1) % btnArray.length];
          next.focus();
          next.click();
        } else if (e.key === 'ArrowLeft') {
          var prev = btnArray[(idx - 1 + btnArray.length) % btnArray.length];
          prev.focus();
          prev.click();
        }
      });
    });
  }

  // ==========================================================================
  // 3. WHATSAPP ADMISSIONS CHAT SIMULATOR
  // ==========================================================================
  function initWhatsAppSimulator() {
    var chatBody = document.getElementById('lpSimChatBody');
    var actionBtns = document.querySelectorAll('.lp-chat-quick-btn');
    if (!chatBody || actionBtns.length === 0) return;

    var botResponses = {
      fees: "Our Full-Stack & Data Science certification programs start at ₹35,000 with 0% interest EMI options. An early-bird ₹5,000 scholarship is active for this week's cohort. Would you like to review the installment schedule?",
      syllabus: "📄 Detailed 2026 Curriculum Syllabus (PDF) generated!\nCovers: Python, Django, React, Cloud Deployments, and 12 Live Real-World Capstone Projects. Download link sent to your WhatsApp.",
      counselor: "🎓 Senior Counselor Arun has been reserved for your personalized 1-on-1 career consultation at 4:30 PM today. A reminder token #TK-108 has been dispatched to your mobile."
    };

    window.triggerSimWhatsApp = function (actionKey) {
      var promptMap = {
        fees: "💰 What are the course fees and available installments?",
        syllabus: "📄 Please send me the 2026 syllabus PDF",
        counselor: "🎓 Connect me with a senior career counselor"
      };

      var userText = promptMap[actionKey] || "Tell me more about enrollments";
      var botText = botResponses[actionKey] || "Thank you for reaching out! A counselor will be in touch shortly.";

      // Append user bubble
      var userBubble = document.createElement('div');
      userBubble.className = 'lp-chat-bubble user';
      userBubble.textContent = userText;
      chatBody.appendChild(userBubble);
      chatBody.scrollTop = chatBody.scrollHeight;

      // Typing simulation
      var typingBubble = document.createElement('div');
      typingBubble.className = 'lp-chat-bubble bot';
      typingBubble.textContent = "Typing...";
      chatBody.appendChild(typingBubble);
      chatBody.scrollTop = chatBody.scrollHeight;

      setTimeout(function () {
        typingBubble.textContent = botText;
        chatBody.scrollTop = chatBody.scrollHeight;
      }, 600);
    };
  }

  // ==========================================================================
  // 4. ADMISSIONS GROWTH & RECOVERY CALCULATOR
  // ==========================================================================
  function initAdmissionsCalculator() {
    var sliderLeads = document.getElementById('lpCalcLeads');
    var sliderMissed = document.getElementById('lpCalcMissed');
    var sliderFee = document.getElementById('lpCalcFee');
    var dispLeads = document.getElementById('lpDispLeads');
    var dispMissed = document.getElementById('lpDispMissed');
    var dispFee = document.getElementById('lpDispFee');
    var dispResult = document.getElementById('lpCalcResult');
    var dispAdmissions = document.getElementById('lpCalcAdmissions');

    if (!sliderLeads || !sliderMissed || !sliderFee || !dispResult) return;

    function formatINR(val) {
      return '₹' + Math.round(val).toLocaleString('en-IN');
    }

    function calculate() {
      var leads = parseInt(sliderLeads.value, 10) || 500;
      var missedPct = parseInt(sliderMissed.value, 10) || 20;
      var fee = parseInt(sliderFee.value, 10) || 35000;
      var conversionRate = 0.15; // Realistic 15% conversion rate on recovered leads

      dispLeads.textContent = leads.toLocaleString('en-IN');
      dispMissed.textContent = missedPct + '%';
      dispFee.textContent = formatINR(fee);

      var missedLeadsCount = leads * (missedPct / 100);
      var recoveredAdmissions = missedLeadsCount * conversionRate;
      var recoveredRevenue = recoveredAdmissions * fee;

      dispResult.textContent = formatINR(recoveredRevenue);
      if (dispAdmissions) {
        dispAdmissions.textContent = '+' + Math.round(recoveredAdmissions) + ' Additional Student Admissions / Month';
      }
    }

    sliderLeads.addEventListener('input', calculate);
    sliderMissed.addEventListener('input', calculate);
    sliderFee.addEventListener('input', calculate);

    calculate();
  }

  // ==========================================================================
  // 5. FAQ ACCORDION
  // ==========================================================================
  function initFaqAccordion() {
    var faqItems = document.querySelectorAll('.lp-faq-item');
    if (faqItems.length === 0) return;

    faqItems.forEach(function (item) {
      var trigger = item.querySelector('.lp-faq-trigger');
      var content = item.querySelector('.lp-faq-content');
      if (!trigger || !content) return;

      trigger.addEventListener('click', function () {
        var isOpen = item.classList.contains('is-open');

        // Close other items
        faqItems.forEach(function (other) {
          other.classList.remove('is-open');
          var tr = other.querySelector('.lp-faq-trigger');
          if (tr) tr.setAttribute('aria-expanded', 'false');
        });

        if (!isOpen) {
          item.classList.add('is-open');
          trigger.setAttribute('aria-expanded', 'true');
        }
      });
    });
  }
})();
