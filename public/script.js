// ── Copy Command ───────────────────────────────────────────────
function copyCommand() {
    const commandText = document.getElementById("install-cmd").innerText;
    navigator.clipboard.writeText(commandText).then(() => {
        const copyBtn = document.querySelector(".copy-btn");
        const copyIcon = copyBtn.querySelector("i");
        copyIcon.className = "fa-solid fa-check";
        copyIcon.style.color = "#10b981";
        setTimeout(() => {
            copyIcon.className = "fa-regular fa-copy";
            copyIcon.style.color = "";
        }, 2000);
    }).catch(err => console.error("Failed to copy:", err));
}

// ── Razorpay Checkout Flow (PRESERVED — do not modify) ─────────
async function handleCheckout(planType) {
    window.location.href = `/api/auth/login?plan=${planType}`;
}

// ── Scroll Progress Bar ────────────────────────────────────────
function initScrollProgress() {
    const bar = document.getElementById('scroll-progress');
    if (!bar) return;
    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY;
        const max = document.body.scrollHeight - window.innerHeight;
        bar.style.width = ((scrolled / max) * 100).toFixed(2) + '%';
    }, { passive: true });
}

// ── Counter Animation ──────────────────────────────────────────
function animateCounter(el, target, suffix = '', duration = 1800) {
    const start = performance.now();
    const isDecimal = target % 1 !== 0;
    function step(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out expo
        const eased = 1 - Math.pow(2, -10 * progress);
        const current = Math.round(eased * target);
        el.textContent = (isDecimal ? current.toFixed(1) : current) + suffix;
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target + suffix;
    }
    requestAnimationFrame(step);
}

// ── 3D Magnetic Tilt on Cards ──────────────────────────────────
function init3DTilt() {
    const cards = document.querySelectorAll('.bento-card, .price-card');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = (e.clientX - cx) / (rect.width / 2);
            const dy = (e.clientY - cy) / (rect.height / 2);
            const tiltX = dy * -6;
            const tiltY = dx * 6;
            card.style.transform = `perspective(900px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateY(-4px) scale(1.02)`;
            // Update card glow origin
            card.style.setProperty('--card-x', `${e.clientX - rect.left}px`);
            card.style.setProperty('--card-y', `${e.clientY - rect.top}px`);
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
}

// ── Magnetic Button Effect ─────────────────────────────────────
function initMagneticButtons() {
    const btns = document.querySelectorAll('.hero-actions .btn');
    btns.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = (e.clientX - cx) * 0.25;
            const dy = (e.clientY - cy) * 0.25;
            btn.style.transform = `translate(${dx}px, ${dy}px) scale(1.05)`;
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = '';
        });
    });
}

// ── Section title word-split animation ────────────────────────
function initSplitTitles() {
    document.querySelectorAll('.section-title').forEach(el => {
        const words = el.textContent.trim().split(' ');
        el.innerHTML = words.map((w, i) =>
            `<span class="reveal-text reveal-delay-${(i % 3) + 1}" style="display:inline-block;margin-right:0.25em;">
                <span class="reveal-inner">${w}</span>
             </span>`
        ).join('');
    });
}

// ── Parallax on aurora orbs ────────────────────────────────────
function initParallax() {
    const orbs = document.querySelectorAll('.orb');
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const y = window.scrollY;
                orbs.forEach((orb, i) => {
                    const speed = [0.04, -0.03, 0.06, -0.02][i] || 0.03;
                    orb.style.transform = `translateY(${y * speed}px)`;
                });
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

// ── Scroll Reveal Observer ─────────────────────────────────────
function initReveal() {
    // Add reveal-fade to bento cards and price cards automatically
    document.querySelectorAll('.bento-card, .price-card').forEach(el => {
        if (!el.classList.contains('reveal-fade')) el.classList.add('reveal-fade');
    });

    const reveals = document.querySelectorAll('.reveal-fade, .reveal-text');
    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                obs.unobserve(entry.target);
            }
        });
    }, { threshold: 0.06, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(el => observer.observe(el));
}

// ── Custom Cursor & Glow ───────────────────────────────────────
function initCursor() {
    const cursorGlow = document.querySelector('.cursor-glow');
    const curDot = document.querySelector('.cur-dot');
    if (!cursorGlow && !curDot) return;

    let mouseX = 0, mouseY = 0;
    let currentX = 0, currentY = 0;
    let cursorInitialized = false;

    document.addEventListener('mousemove', (e) => {
        if (!cursorInitialized) {
            mouseX = currentX = e.clientX;
            mouseY = currentY = e.clientY;
            if (curDot) curDot.style.opacity = '1';
            if (cursorGlow) cursorGlow.style.opacity = '1';
            cursorInitialized = true;
        }
        mouseX = e.clientX;
        mouseY = e.clientY;
        if (cursorGlow) cursorGlow.style.opacity = '1';
    });

    document.addEventListener('mouseleave', () => {
        if (cursorGlow) cursorGlow.style.opacity = '0';
        if (curDot) curDot.style.opacity = '0';
    });

    const interactives = document.querySelectorAll('a, button, .bento-card, .price-card');
    interactives.forEach(el => {
        const isCard = el.classList.contains('bento-card') || el.classList.contains('price-card');
        el.addEventListener('mouseenter', () => {
            if (cursorGlow) cursorGlow.classList.add('glow-active');
            if (curDot && !isCard) curDot.classList.add('big');
        });
        el.addEventListener('mouseleave', () => {
            if (cursorGlow) cursorGlow.classList.remove('glow-active');
            if (curDot) curDot.classList.remove('big');
        });
    });

    function animateGlow() {
        if (curDot) {
            curDot.style.transform = `translate(-50%, -50%) translate3d(${mouseX}px, ${mouseY}px, 0)`;
        }
        if (cursorGlow) {
            currentX += (mouseX - currentX) * 0.08;
            currentY += (mouseY - currentY) * 0.08;
            cursorGlow.style.setProperty('--mouse-x', currentX);
            cursorGlow.style.setProperty('--mouse-y', currentY);
        }
        requestAnimationFrame(animateGlow);
    }
    animateGlow();
}

// ── Live Stats ─────────────────────────────────────────────────
function initLiveStats() {
    // GitHub Stars
    fetch('https://api.github.com/repos/RajX-dev/N3MO')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('gh-stars');
            if (el && data.stargazers_count != null) {
                const count = data.stargazers_count;
                // Animate to value when visible
                const obs = new IntersectionObserver(entries => {
                    if (entries[0].isIntersecting) {
                        animateCounter(el, count, '');
                        obs.disconnect();
                    }
                }, { threshold: 0.5 });
                obs.observe(el);
            }
        })
        .catch(() => {
            const el = document.getElementById('gh-stars');
            if (el) el.textContent = '900+';
        });

    // PyPI Downloads
    fetch('https://api.pepy.tech/api/v2/projects/n3mo')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('pypi-downloads');
            if (el && data.total_downloads != null) {
                const count = data.total_downloads;
                const obs = new IntersectionObserver(entries => {
                    if (entries[0].isIntersecting) {
                        const displayVal = count >= 1000 ? Math.floor(count / 1000) : count;
                        const suffix = count >= 1000 ? 'K+' : '';
                        animateCounter(el, displayVal, suffix);
                        obs.disconnect();
                    }
                }, { threshold: 0.5 });
                obs.observe(el);
            }
        })
        .catch(() => {
            const el = document.getElementById('pypi-downloads');
            if (el) el.textContent = '12K+';
        });

    // Edges indexed — count up from 0 to 480K
    const edgesEl = document.getElementById('edges-count');
    if (edgesEl) {
        const obs = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                animateCounter(edgesEl, 480, 'K');
                obs.disconnect();
            }
        }, { threshold: 0.5 });
        obs.observe(edgesEl);
    }
}

// ── Auth check ─────────────────────────────────────────────────
function initAuth() {
    fetch('/api/auth/me', { credentials: 'include' })
        .then(res => {
            const navCta = document.querySelector('.nav-cta');
            if (!navCta) return;
            if (res.ok) {
                const btn = document.createElement('a');
                btn.href = 'dashboard.html';
                btn.className = 'btn btn-primary';
                btn.innerHTML = '<i class="fa-solid fa-chart-line"></i> Dashboard';
                btn.style.cssText = 'margin-right:8px;padding:7px 14px;border-radius:6px;font-size:12.5px;animation:none;';
                navCta.prepend(btn);
            } else {
                const btn = document.createElement('a');
                btn.href = '/api/auth/login';
                btn.className = 'btn btn-outline';
                btn.innerHTML = '<i class="fa-brands fa-github"></i> Sign In';
                btn.style.cssText = 'margin-right:8px;padding:7px 14px;border-radius:6px;font-size:12.5px;animation:none;';
                navCta.prepend(btn);
            }
        })
        .catch(() => {});
}

// ── Hero CTA primary button — id-based scroll to pricing ───────
function initHeroCTA() {
    const cta = document.getElementById('hero-cta-primary');
    if (cta) {
        cta.addEventListener('click', (e) => {
            // Only intercept if not logged in (dashboard link handled by auth)
            if (cta.href && cta.href.includes('dashboard')) return;
        });
    }
}

// ── Apple-Grade Ambient Background Dynamics ────────────────────
function initAppleBackground() {
    const mouseGlow = document.getElementById('apple-mouse-glow');
    if (!mouseGlow) return;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 2;
    let currentX = targetX;
    let currentY = targetY;
    let isMouseActive = false;
    let animId = null;

    function renderGlow() {
        currentX += (targetX - currentX) * 0.08;
        currentY += (targetY - currentY) * 0.08;

        mouseGlow.style.left = `${currentX}px`;
        mouseGlow.style.top = `${currentY}px`;

        if (Math.abs(targetX - currentX) > 0.1 || Math.abs(targetY - currentY) > 0.1) {
            animId = requestAnimationFrame(renderGlow);
        } else {
            animId = null;
        }
    }

    window.addEventListener('mousemove', (e) => {
        targetX = e.clientX;
        targetY = e.clientY;
        if (!isMouseActive) {
            mouseGlow.style.opacity = '1';
            isMouseActive = true;
        }
        if (!animId) {
            animId = requestAnimationFrame(renderGlow);
        }
    }, { passive: true });

    document.addEventListener('mouseleave', () => {
        mouseGlow.style.opacity = '0';
        isMouseActive = false;
    });
}

// ── Three.js 3D Animated Lava Lamp Footer ──────────────────────
function initThreeJsFooter() {
    const canvas = document.getElementById('footer-three-canvas');
    const footer = document.querySelector('footer');
    if (!canvas || !footer) return;

    function loadThreeScript(cb) {
        if (window.THREE) {
            cb();
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
        script.async = true;
        script.onload = () => cb();
        script.onerror = () => console.warn('Could not load Three.js from CDN.');
        document.head.appendChild(script);
    }

    loadThreeScript(() => {
        if (!window.THREE) return;
        buildLavaLampScene();
    });

    function buildLavaLampScene() {
        const THREE = window.THREE;

        const scene = new THREE.Scene();
        const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

        let renderer;
        try {
            renderer = new THREE.WebGLRenderer({
                canvas: canvas,
                alpha: true,
                antialias: true,
                powerPreference: 'high-performance'
            });
        } catch (e) {
            console.warn('WebGL not supported for Three.js footer:', e);
            return;
        }

        const width = footer.clientWidth || window.innerWidth;
        const height = footer.clientHeight || 340;
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const uniforms = {
            u_time: { value: 0.0 },
            u_resolution: { value: new THREE.Vector2(width, height) },
            u_mouse: { value: new THREE.Vector2(0.0, 0.0) },
            u_mouse_active: { value: 0.0 }
        };

        const vertexShader = `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = vec4(position, 1.0);
            }
        `;

        const fragmentShader = `
            precision highp float;
            varying vec2 vUv;
            uniform vec2 u_resolution;
            uniform float u_time;
            uniform vec2 u_mouse;
            uniform float u_mouse_active;

            // Polynomial smooth minimum for organic metaball liquid fusion
            float smin(float a, float b, float k) {
                float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
                return mix(b, a, h) - k * h * (1.0 - h);
            }

            // Sphere distance field
            float sdSphere(vec3 p, float r) {
                return length(p) - r;
            }

            // Raymarched Lava Lamp scene map across full widescreen
            float map(vec3 p, out vec3 fluidColor) {
                float t = u_time * 0.7;

                // ── Group 1: Far Left (-7.5 to -4.8) ──
                vec3 b1 = vec3(
                    -6.2 + sin(t * 0.45) * 1.1,
                    sin(t * 0.6) * 1.4,
                    cos(t * 0.35) * 0.6
                );
                vec3 p1 = p - b1; p1.y *= 0.9 + 0.12 * sin(t * 1.1);
                float d1 = sdSphere(p1, 1.35 + 0.12 * sin(t * 0.9));

                vec3 b2 = vec3(
                    -5.0 + cos(t * 0.5 + 1.0) * 0.9,
                    cos(t * 0.75 + 2.0) * 1.5,
                    sin(t * 0.4) * 0.5
                );
                vec3 p2 = p - b2; p2.y *= 0.88 + 0.14 * cos(t * 1.3);
                float d2 = sdSphere(p2, 1.15 + 0.1 * cos(t * 1.2));

                // ── Group 2: Mid Left (-4.8 to -2.0) ──
                vec3 b3 = vec3(
                    -3.4 + sin(t * 0.4 + 2.5) * 1.0,
                    sin(t * 0.65 + 3.0) * 1.5,
                    cos(t * 0.5) * 0.6
                );
                vec3 p3 = p - b3; p3.y *= 0.85 + 0.15 * sin(t * 1.4);
                float d3 = sdSphere(p3, 1.4 + 0.12 * sin(t * 0.8));

                vec3 b4 = vec3(
                    -2.2 + cos(t * 0.8 + 0.5) * 0.8,
                    cos(t * 0.9 + 1.5) * 1.4,
                    sin(t * 0.6 + 1.0) * 0.5
                );
                float d4 = sdSphere(p - b4, 0.95 + 0.08 * sin(t * 1.8));

                // ── Group 3: Center (-2.0 to +2.0) ──
                vec3 b5 = vec3(
                    -0.8 + sin(t * 0.5 + 1.2) * 0.9,
                    cos(t * 0.55 + 0.8) * 1.5,
                    sin(t * 0.35) * 0.7
                );
                vec3 p5 = p - b5; p5.y *= 0.92 + 0.12 * sin(t * 1.0);
                float d5 = sdSphere(p5, 1.45 + 0.15 * sin(t * 0.7));

                vec3 b6 = vec3(
                    0.9 + cos(t * 0.45 + 3.2) * 1.0,
                    sin(t * 0.7 + 2.2) * 1.5,
                    cos(t * 0.4) * 0.6
                );
                vec3 p6 = p - b6; p6.y *= 0.86 + 0.14 * cos(t * 1.2);
                float d6 = sdSphere(p6, 1.35 + 0.12 * cos(t * 0.9));

                // ── Group 4: Mid Right (+2.0 to +4.8) ──
                vec3 b7 = vec3(
                    2.8 + sin(t * 0.55 + 4.0) * 1.0,
                    cos(t * 0.65 + 1.8) * 1.5,
                    sin(t * 0.5) * 0.6
                );
                vec3 p7 = p - b7; p7.y *= 0.88 + 0.15 * sin(t * 1.3);
                float d7 = sdSphere(p7, 1.3 + 0.12 * sin(t * 1.1));

                vec3 b8 = vec3(
                    4.0 + cos(t * 0.7 + 2.0) * 0.8,
                    sin(t * 0.85 + 0.5) * 1.4,
                    cos(t * 0.6 + 2.0) * 0.5
                );
                float d8 = sdSphere(p - b8, 1.0 + 0.08 * cos(t * 1.6));

                // ── Group 5: Far Right (+4.8 to +7.5) ──
                vec3 b9 = vec3(
                    5.5 + sin(t * 0.4 + 1.8) * 1.1,
                    sin(t * 0.6 + 4.2) * 1.5,
                    cos(t * 0.45) * 0.6
                );
                vec3 p9 = p - b9; p9.y *= 0.9 + 0.14 * sin(t * 1.2);
                float d9 = sdSphere(p9, 1.4 + 0.12 * sin(t * 0.85));

                vec3 b10 = vec3(
                    6.6 + cos(t * 0.5 + 3.0) * 0.9,
                    cos(t * 0.7 + 1.2) * 1.4,
                    sin(t * 0.35) * 0.5
                );
                float d10 = sdSphere(p - b10, 1.1 + 0.1 * cos(t * 1.5));

                // ── Full-Width Melting Bottom Reservoirs ──
                float dPoolBottom = sdSphere(p - vec3(-5.5, -2.4 + 0.15 * sin(t * 0.5), 0.0), 1.7);
                dPoolBottom = smin(dPoolBottom, sdSphere(p - vec3(-2.2, -2.4 + 0.15 * cos(t * 0.6), 0.0), 1.7), 1.1);
                dPoolBottom = smin(dPoolBottom, sdSphere(p - vec3(0.8, -2.4 + 0.15 * sin(t * 0.7), 0.0), 1.7), 1.1);
                dPoolBottom = smin(dPoolBottom, sdSphere(p - vec3(4.0, -2.4 + 0.15 * cos(t * 0.5), 0.0), 1.7), 1.1);
                dPoolBottom = smin(dPoolBottom, sdSphere(p - vec3(6.5, -2.4 + 0.15 * sin(t * 0.6), 0.0), 1.7), 1.1);

                // ── Full-Width Cooling Top Reservoirs ──
                float dPoolTop = sdSphere(p - vec3(-5.5, 2.4 + 0.15 * cos(t * 0.5), 0.0), 1.6);
                dPoolTop = smin(dPoolTop, sdSphere(p - vec3(-2.0, 2.4 + 0.15 * sin(t * 0.6), 0.0), 1.6), 1.1);
                dPoolTop = smin(dPoolTop, sdSphere(p - vec3(1.2, 2.4 + 0.15 * cos(t * 0.7), 0.0), 1.6), 1.1);
                dPoolTop = smin(dPoolTop, sdSphere(p - vec3(4.5, 2.4 + 0.15 * sin(t * 0.5), 0.0), 1.6), 1.1);
                dPoolTop = smin(dPoolTop, sdSphere(p - vec3(6.8, 2.4 + 0.15 * cos(t * 0.6), 0.0), 1.6), 1.1);

                // ── Interactive Mouse Attractor Heat Blob (reaches full widescreen) ──
                vec3 bMouse = vec3(u_mouse.x * 7.5, u_mouse.y * 1.8, 0.1);
                float dMouse = sdSphere(p - bMouse, mix(0.01, 1.2, u_mouse_active));

                // ── Smooth Metaball Fusion ──
                float k = 0.88;
                float d = smin(d1, d2, k);
                d = smin(d, d3, k);
                d = smin(d, d4, k);
                d = smin(d, d5, k);
                d = smin(d, d6, k);
                d = smin(d, d7, k);
                d = smin(d, d8, k);
                d = smin(d, d9, k);
                d = smin(d, d10, k);
                d = smin(d, dPoolBottom, 1.1);
                d = smin(d, dPoolTop, 1.1);
                d = smin(d, dMouse, 0.92);

                // ── Chromatic Molten Color Waves ──
                vec3 colAmber  = vec3(1.0, 0.52, 0.03);   // Warm molten gold/amber #f59e0b
                vec3 colViolet = vec3(0.55, 0.32, 1.0);    // Deep electric violet #8b5cf6
                vec3 colCyan   = vec3(0.02, 0.85, 0.98);   // Radiant cyan #00d2ff
                vec3 colRose   = vec3(0.98, 0.22, 0.46);   // Molten magma rose #f43f5e
                vec3 colGreen  = vec3(0.16, 0.90, 0.44);   // Emerald spark #32d74b

                float w1 = max(0.001, 1.0 - length(p - b1) / 2.6);
                float w2 = max(0.001, 1.0 - length(p - b3) / 2.6);
                float w3 = max(0.001, 1.0 - length(p - b5) / 2.8);
                float w4 = max(0.001, 1.0 - length(p - b6) / 2.6);
                float w5 = max(0.001, 1.0 - length(p - b7) / 2.6);
                float w6 = max(0.001, 1.0 - length(p - b9) / 2.8);
                float wm = max(0.001, (1.0 - length(p - bMouse) / 2.4) * u_mouse_active);

                fluidColor = (w1 * colAmber + w2 * colCyan + w3 * colRose + w4 * colViolet + w5 * colGreen + w6 * colAmber + wm * colAmber)
                           / (w1 + w2 + w3 + w4 + w5 + w6 + wm);

                return d;
            }

            vec3 calcNormal(vec3 p) {
                vec2 e = vec2(0.003, 0.0);
                vec3 temp;
                return normalize(vec3(
                    map(p + e.xyy, temp) - map(p - e.xyy, temp),
                    map(p + e.yxy, temp) - map(p - e.yxy, temp),
                    map(p + e.yyx, temp) - map(p - e.yyx, temp)
                ));
            }

            void main() {
                vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);

                vec3 ro = vec3(0.0, 0.0, 5.2);
                vec3 rd = normalize(vec3(uv, -1.35));

                float t = 0.0;
                float hit = 0.0;
                vec3 fluidCol = vec3(0.0);
                vec3 p;

                for (int i = 0; i < 54; i++) {
                    p = ro + rd * t;
                    float d = map(p, fluidCol);
                    if (d < 0.003) {
                        hit = 1.0;
                        break;
                    }
                    t += max(d * 0.72, 0.022);
                    if (t > 12.0) break;
                }

                vec3 col = vec3(0.0);

                if (hit > 0.5) {
                    vec3 norm = calcNormal(p);
                    vec3 viewDir = -rd;

                    // Internal dynamic chamber lights spanning widescreen
                    vec3 lightPos1 = vec3(sin(u_time * 0.6) * 5.0, 2.0, 3.0);
                    vec3 lightDir1 = normalize(lightPos1 - p);
                    float diff1 = max(0.0, dot(norm, lightDir1));

                    vec3 lightPos2 = vec3(-sin(u_time * 0.5) * 5.0, -2.5, 2.5);
                    vec3 lightDir2 = normalize(lightPos2 - p);
                    float diff2 = max(0.0, dot(norm, lightDir2));

                    // Specular glass highlights
                    vec3 halfVec1 = normalize(lightDir1 + viewDir);
                    float spec1 = pow(max(0.0, dot(norm, halfVec1)), 36.0);

                    // Liquid Fresnel rim glow
                    float fresnel = pow(1.0 - max(0.0, dot(norm, viewDir)), 2.5);

                    // Multi-layer molten liquid luminescence
                    vec3 ambientGlow = fluidCol * 0.78;
                    vec3 diffuseGlow = fluidCol * (diff1 * 0.75 + diff2 * 0.45);
                    vec3 rimGlow = mix(fluidCol, vec3(1.0, 0.96, 0.85), 0.5) * fresnel * 2.4;
                    vec3 specGlow = vec3(1.0, 0.95, 0.85) * spec1 * 0.95;

                    col = ambientGlow + diffuseGlow + rimGlow + specGlow;
                }

                // Ambient fluid chamber dispersion
                float bgDist = length(uv);
                vec3 bgFluidGlow = vec3(0.03, 0.02, 0.05) + vec3(0.05, 0.025, 0.01) * exp(-bgDist * 1.5);
                col += bgFluidGlow * (1.0 - hit);

                // Smooth top/bottom vertical alpha feathering
                float vertPos = gl_FragCoord.y / u_resolution.y;
                float alphaFade = smoothstep(0.0, 0.05, vertPos) * smoothstep(1.0, 0.95, vertPos);

                gl_FragColor = vec4(col * alphaFade, alphaFade * (hit > 0.5 ? 0.98 : 0.45));
            }
        `;

        const material = new THREE.ShaderMaterial({
            vertexShader: vertexShader,
            fragmentShader: fragmentShader,
            uniforms: uniforms,
            transparent: true,
            depthWrite: false
        });

        const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
        scene.add(quad);

        // Mouse coordinates tracking
        let targetMouseX = 0;
        let targetMouseY = 0;
        let currMouseX = 0;
        let currMouseY = 0;
        let mouseActiveTarget = 0;
        let mouseActiveCurr = 0;

        footer.addEventListener('mousemove', (e) => {
            const rect = footer.getBoundingClientRect();
            targetMouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            targetMouseY = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
            mouseActiveTarget = 1.0;
        }, { passive: true });

        footer.addEventListener('mouseleave', () => {
            mouseActiveTarget = 0.0;
        });

        function onResize() {
            const w = footer.clientWidth || window.innerWidth;
            const h = footer.clientHeight || 340;
            renderer.setSize(w, h);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            uniforms.u_resolution.value.set(w, h);
        }

        window.addEventListener('resize', onResize, { passive: true });

        // Animation Loop & Performance Guard
        let isVisible = true;
        let clock = 0;
        let animFrameId = null;

        function animate() {
            if (!isVisible) return;

            clock += 0.018;
            uniforms.u_time.value = clock;

            // Smooth mouse damping
            currMouseX += (targetMouseX - currMouseX) * 0.08;
            currMouseY += (targetMouseY - currMouseY) * 0.08;
            mouseActiveCurr += (mouseActiveTarget - mouseActiveCurr) * 0.06;

            uniforms.u_mouse.value.set(currMouseX, currMouseY);
            uniforms.u_mouse_active.value = mouseActiveCurr;

            renderer.render(scene, camera);
            animFrameId = requestAnimationFrame(animate);
        }

        const observer = new IntersectionObserver((entries) => {
            const entry = entries[0];
            if (entry.isIntersecting) {
                if (!isVisible) {
                    isVisible = true;
                    onResize();
                    animate();
                }
            } else {
                isVisible = false;
                if (animFrameId) {
                    cancelAnimationFrame(animFrameId);
                    animFrameId = null;
                }
            }
        }, { threshold: 0.05 });

        observer.observe(footer);
        animate();
    }
}

// ── Init all ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initScrollProgress();
    initSplitTitles();
    initReveal();
    init3DTilt();
    initMagneticButtons();
    initParallax();
    initLiveStats();
    initAuth();
    initHeroCTA();
    initCursor();
    initAppleBackground();
    initThreeJsFooter();
});
