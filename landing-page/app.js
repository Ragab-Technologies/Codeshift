// ============================================
// PyResolve Landing Page - Supabase Integration
// ============================================

// Supabase configuration for waitlist signups
// The anon key is safe for client-side use (it's a publishable key)
const SUPABASE_URL = 'https://ztpklncwerkbycbtjszd.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable__xjS65qhfWLbJf6EHJPb2Q_qsxufF_i';

// Initialize Supabase client
let supabase = null;

function initSupabase() {
    if (SUPABASE_URL === 'YOUR_SUPABASE_URL' || SUPABASE_ANON_KEY === 'YOUR_SUPABASE_ANON_KEY') {
        console.warn('Supabase credentials not configured. Please update SUPABASE_URL and SUPABASE_ANON_KEY in app.js');
        return false;
    }

    try {
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        return true;
    } catch (error) {
        console.error('Failed to initialize Supabase:', error);
        return false;
    }
}

// ============================================
// Form Handling
// ============================================

async function handleFormSubmit(event, formId) {
    event.preventDefault();

    const isTopForm = formId === 'waitlist-form';
    const emailInput = document.getElementById(isTopForm ? 'email-input' : 'email-input-bottom');
    const submitBtn = document.getElementById(isTopForm ? 'submit-btn' : 'submit-btn-bottom');
    const form = document.getElementById(formId);
    const successMessage = document.getElementById(isTopForm ? 'success-message' : 'success-message-bottom');

    const email = emailInput.value.trim();

    if (!email || !isValidEmail(email)) {
        shakeElement(emailInput);
        return;
    }

    // Show loading state
    setLoadingState(submitBtn, true);

    try {
        // If Supabase is configured, save to database
        if (supabase) {
            const { error } = await supabase
                .from('waitlist')
                .insert([
                    {
                        email: email,
                        source: 'landing_page',
                        created_at: new Date().toISOString()
                    }
                ]);

            if (error) {
                // Check if it's a duplicate email error
                if (error.code === '23505') {
                    // Email already exists - still show success
                    console.log('Email already on waitlist');
                } else {
                    throw error;
                }
            }
        } else {
            // Demo mode - just simulate a delay
            console.log('Demo mode: Email would be saved:', email);
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        // Show success state
        form.style.display = 'none';
        successMessage.style.display = 'flex';

        // Track conversion (if analytics is set up)
        trackConversion(email);

    } catch (error) {
        console.error('Error saving email:', error);
        alert('Something went wrong. Please try again.');
    } finally {
        setLoadingState(submitBtn, false);
    }
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function setLoadingState(button, isLoading) {
    const btnText = button.querySelector('.btn-text');
    const btnLoading = button.querySelector('.btn-loading');

    if (isLoading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        button.disabled = true;
    } else {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        button.disabled = false;
    }
}

function shakeElement(element) {
    element.style.animation = 'none';
    element.offsetHeight; // Trigger reflow
    element.style.animation = 'shake 0.5s ease-in-out';

    setTimeout(() => {
        element.style.animation = 'none';
    }, 500);
}

// Add shake animation to document
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
        20%, 40%, 60%, 80% { transform: translateX(5px); }
    }
`;
document.head.appendChild(style);

// ============================================
// Analytics (optional)
// ============================================

function trackConversion(email) {
    // Google Analytics 4
    if (typeof gtag !== 'undefined') {
        gtag('event', 'sign_up', {
            method: 'waitlist'
        });
    }

    // Plausible
    if (typeof plausible !== 'undefined') {
        plausible('Waitlist Signup');
    }

    // PostHog
    if (typeof posthog !== 'undefined') {
        posthog.capture('waitlist_signup', {
            email_domain: email.split('@')[1]
        });
    }

    console.log('Conversion tracked for:', email);
}

// ============================================
// Smooth Scroll for Anchor Links
// ============================================

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// ============================================
// Navbar Background on Scroll
// ============================================

function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.style.background = 'rgba(10, 10, 11, 0.95)';
        } else {
            navbar.style.background = 'rgba(10, 10, 11, 0.8)';
        }
    });
}

// ============================================
// Terminal Animation (optional enhancement)
// ============================================

function initTerminalAnimation() {
    const terminalOutput = document.querySelector('.terminal-output');
    if (!terminalOutput) return;

    const lines = terminalOutput.querySelectorAll('span');

    // Hide all lines initially
    lines.forEach(line => {
        line.style.opacity = '0';
        line.style.transform = 'translateY(10px)';
        line.style.transition = 'opacity 0.3s, transform 0.3s';
    });

    // Observe when terminal comes into view
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Animate lines one by one
                lines.forEach((line, index) => {
                    setTimeout(() => {
                        line.style.opacity = '1';
                        line.style.transform = 'translateY(0)';
                    }, index * 150);
                });
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    observer.observe(terminalOutput);
}

// ============================================
// Feature Cards Animation
// ============================================

function initCardAnimations() {
    const cards = document.querySelectorAll('.feature-card, .step-card');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s, transform 0.5s';
        observer.observe(card);
    });
}

// ============================================
// Initialize Everything
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Supabase
    initSupabase();

    // Set up form handlers
    const topForm = document.getElementById('waitlist-form');
    const bottomForm = document.getElementById('waitlist-form-bottom');

    if (topForm) {
        topForm.addEventListener('submit', (e) => handleFormSubmit(e, 'waitlist-form'));
    }

    if (bottomForm) {
        bottomForm.addEventListener('submit', (e) => handleFormSubmit(e, 'waitlist-form-bottom'));
    }

    // Initialize UI enhancements
    initSmoothScroll();
    initNavbarScroll();
    initTerminalAnimation();
    initCardAnimations();

    console.log('PyResolve landing page initialized');
});

// ============================================
// SETUP INSTRUCTIONS
// ============================================
/*

1. CREATE A SUPABASE PROJECT
   - Go to https://supabase.com
   - Create a new project
   - Wait for it to initialize

2. CREATE THE WAITLIST TABLE
   Run this SQL in the Supabase SQL Editor:

   CREATE TABLE waitlist (
       id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
       email TEXT UNIQUE NOT NULL,
       source TEXT DEFAULT 'landing_page',
       created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );

   -- Enable Row Level Security
   ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

   -- Create a policy to allow inserts from anonymous users
   CREATE POLICY "Allow anonymous inserts" ON waitlist
       FOR INSERT
       TO anon
       WITH CHECK (true);

   -- Create an index on email for faster lookups
   CREATE INDEX idx_waitlist_email ON waitlist(email);

3. GET YOUR API CREDENTIALS
   - Go to Project Settings > API
   - Copy your "Project URL" and "anon public" key
   - Replace SUPABASE_URL and SUPABASE_ANON_KEY at the top of this file

4. TEST THE FORM
   - Open the landing page in a browser
   - Submit a test email
   - Check the waitlist table in Supabase

*/
