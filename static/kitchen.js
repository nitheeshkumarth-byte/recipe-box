(() => {
    const width = 1200;
    const height = 740;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "Overhead view of chefs at the stove, prep tables, and plating counter.");
    const scene = canvas.getContext("2d");
    if (!scene || typeof HTMLDialogElement.prototype.showModal !== "function") return;

    document.body.insertAdjacentHTML("afterbegin", `
        <div class="kitchen-backdrop" aria-hidden="true"></div>
        <button class="kitchen-door" type="button" aria-haspopup="dialog" aria-controls="executive-kitchen">
            <span>Enter kitchen</span>
        </button>
        <dialog class="kitchen-observation" id="executive-kitchen" aria-labelledby="kitchen-heading">
            <header>
                <h2 id="kitchen-heading">The Executive Kitchen</h2>
                <button class="kitchen-motion" type="button">Pause motion</button>
                <button class="kitchen-exit" type="button" autofocus>Back to recipes</button>
            </header>
        </dialog>`);
    document.body.classList.add("kitchen-page");
    const backdrop = document.querySelector(".kitchen-backdrop");
    const siteHeader = document.querySelector("body > header");
    const door = document.querySelector(".kitchen-door");
    const dialog = document.querySelector(".kitchen-observation");
    const motionButton = dialog.querySelector(".kitchen-motion");
    backdrop.append(canvas);

    function maskNavigation() {
        const bottom = Math.max(0, siteHeader.getBoundingClientRect().bottom);
        backdrop.style.setProperty("--kitchen-nav-bottom", `${bottom}px`);
    }

    new ResizeObserver(maskNavigation).observe(siteHeader);
    window.addEventListener("scroll", maskNavigation, { passive: true });
    maskNavigation();

    const plan = document.createElement("canvas");
    plan.width = width;
    plan.height = height;
    const ctx = plan.getContext("2d");

    function rect(context, x, y, w, h, radius, color, stroke) {
        context.beginPath();
        context.roundRect(x, y, w, h, radius);
        context.fillStyle = color;
        context.fill();
        if (stroke) {
            context.strokeStyle = stroke;
            context.stroke();
        }
    }

    function oval(context, x, y, rx, ry, color, stroke) {
        context.beginPath();
        context.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
        context.fillStyle = color;
        context.fill();
        if (stroke) {
            context.strokeStyle = stroke;
            context.stroke();
        }
    }

    function counter(x, y, w, h, wood = false) {
        rect(ctx, x + 4, y + 10, w, h, 8, "#070c0cb3");
        rect(ctx, x, y, w, h, 8, "#202a27", "#161e1c");
        const top = ctx.createLinearGradient(0, y, 0, y + h);
        top.addColorStop(0, wood ? "#aa7950" : "#bec7bc");
        top.addColorStop(.09, wood ? "#90603d" : "#939f95");
        top.addColorStop(.85, wood ? "#775033" : "#667972");
        top.addColorStop(1, wood ? "#60402c" : "#50635c");
        rect(ctx, x + 3, y + 3, w - 6, h - 8, 5, top, wood ? "#c38f5b" : "#b9c5b7");
        for (let screw = x + 13; screw < x + w - 8; screw += 81) {
            oval(ctx, screw, y + h - 10, 2, 2, "#25332d77");
        }
    }

    function board(x, y, garnish) {
        rect(ctx, x, y + 3, 68, 43, 6, "#27302b66");
        rect(ctx, x, y, 68, 43, 6, "#b88b58", "#e1b985");
        rect(ctx, x + 4, y + 4, 60, 35, 4, "#93683e", "#d0a774");
        for (let index = 0; index < 12; index++) {
            oval(ctx, x + 18 + (index * 11) % 28, y + 12 + (index * 7) % 19, 3, 2, garnish);
        }
        rect(ctx, x + 47, y + 16, 15, 5, 1, "#dce1d8");
        rect(ctx, x + 57, y + 16, 9, 5, 1, "#342820");
    }

    function plate(x, y, food) {
        oval(ctx, x + 2, y + 4, 16, 16, "#151d1880");
        oval(ctx, x, y, 16, 16, "#e1d5bc", "#fff6df");
        oval(ctx, x, y, 11, 11, "#f3ead8", "#bfb19c");
        if (food) {
            oval(ctx, x, y, 8, 6, food);
            oval(ctx, x + 3, y - 2, 4, 2, "#7d924e");
            oval(ctx, x - 3, y, 2, 2, "#e8bc65");
        }
    }

    function pan(x, y, food, copper) {
        rect(ctx, x + 12, y - 3, 22, 6, 3, "#2d2520");
        oval(ctx, x, y, 17, 17, copper ? "#ba7649" : "#788681", "#28302a");
        oval(ctx, x, y, 13, 13, "#292722");
        oval(ctx, x - 2, y + 1, 8, 7, food);
        oval(ctx, x + 1, y - 2, 4, 2, "#eed173");
    }

    function sink(x, y) {
        rect(ctx, x, y, 74, 54, 7, "#b0bcb6", "#d0d9ca");
        rect(ctx, x + 5, y + 5, 64, 44, 5, "#4e655f", "#d0d9ca");
        oval(ctx, x + 36, y + 29, 5, 5, "#293c37", "#9aadaa");
        rect(ctx, x + 33, y - 8, 7, 24, 3, "#e0e5d6", "#6f847c");
    }

    ctx.fillStyle = "#151c1c";
    ctx.fillRect(0, 0, width, height);
    rect(ctx, 36, 32, 1128, 676, 15, "#202827", "#695640");
    rect(ctx, 55, 52, 1090, 638, 8, "#46524b", "#b08d60");
    for (let y = 60; y < 682; y += 38) {
        for (let x = 64; x < 1137; x += 40) {
            const shade = [73, 76, 78, 79][(x * 7 + y * 11 + (x * y) % 13) % 4];
            ctx.fillStyle = `rgb(${shade - 8} ${shade} ${shade - 4})`;
            ctx.fillRect(x, y, Math.min(38, 1136 - x), Math.min(36, 682 - y));
        }
    }
    for (const x of [145, 390, 635, 880]) {
        rect(ctx, x, 36, 165, 18, 3, "#6c8880", "#b6bd9f");
        rect(ctx, x + 6, 40, 153, 7, 2, "#9cb3a1");
        rect(ctx, x + 80, 36, 5, 16, 1, "#425851");
    }
    rect(ctx, 41, 337, 21, 108, 3, "#79634a", "#e2bb83");
    rect(ctx, 41, 385, 12, 30, 2, "#d7b374");

    counter(103, 91, 350, 120);
    rect(ctx, 119, 105, 310, 87, 5, "#283530", "#cad0bf");
    for (const x of [151, 217, 283, 349, 399]) {
        oval(ctx, x, 139, 22, 20, "#192420", "#63766c");
        oval(ctx, x, 139, 13, 12, "#37433b", "#1c2b23");
        oval(ctx, x, 181, 3, 3, "#d7aa69");
    }
    pan(151, 138, "#ad6c32", true);
    pan(228, 151, "#bf8a49", false);
    pan(349, 139, "#718549", true);
    rect(ctx, 383, 116, 37, 52, 3, "#432e25", "#66796e");
    for (let y = 122; y < 165; y += 6) rect(ctx, 385, y, 32, 1, 0, "#6d6252");

    counter(478, 91, 330, 120);
    sink(500, 119);
    sink(609, 119);
    for (const x of [715, 746, 776]) plate(x, 143);
    counter(829, 91, 262, 120, true);
    for (const x of [857, 911, 965, 1019]) {
        rect(ctx, x, 123, 43, 54, 5, "#3f4a3c", "#9e9e7a");
        for (let i = 0; i < 6; i++) oval(ctx, x + 11 + (i * 9) % 24, 136 + (i * 7) % 27, 4, 4,
            ["#a2a759", "#bf8052", "#830f24", "#e0be79"][(x + i) % 4]);
    }

    counter(208, 313, 780, 113, true);
    board(255, 342, "#718d53");
    board(394, 342, "#bd4e33");
    board(714, 340, "#dcad4a");
    board(848, 341, "#a6a868");
    for (const x of [514, 554, 594, 634]) plate(x, 369, x === 554 ? "#aa5d48" : null);
    for (const x of [402, 533, 664, 795]) {
        oval(ctx, x, 317, 18, 5, "#e9c8784d");
    }

    counter(88, 466, 94, 172);
    sink(99, 488);
    for (const y of [572, 601]) plate(137, y);
    counter(1016, 315, 89, 200);
    for (const y of [328, 378, 428, 478]) {
        rect(ctx, 1027, y, 65, 27, 3, "#52685d", "#adbbad");
        rect(ctx, 1047, y + 6, 24, 3, 1, "#263730");
    }
    counter(220, 558, 760, 95);
    for (const x of [265, 322, 379, 436, 493, 550, 607, 664, 721, 778, 835, 892, 949]) {
        plate(x, 601, x < 700 ? ["#ad673f", "#9a643e", "#c99a4f"][x % 3] : null);
    }
    for (const x of [300, 451, 602, 753, 904]) {
        const heat = ctx.createRadialGradient(x, 588, 1, x, 588, 55);
        heat.addColorStop(0, "#ffcd7277");
        heat.addColorStop(1, "#ffcd7200");
        oval(ctx, x, 588, 55, 45, heat);
        rect(ctx, x - 15, 560, 30, 7, 2, "#b99661", "#ebc589");
    }
    ctx.font = "600 10px system-ui";
    ctx.textAlign = "center";
    ctx.letterSpacing = "2px";
    ctx.fillStyle = "#e5d2ad";
    for (const [label, x, y] of [["HOT LINE", 278, 76], ["WASH", 645, 76], ["PANTRY", 960, 76],
        ["PREPARATION", 598, 337], ["SERVICE PASS", 600, 676]]) {
        ctx.fillText(label, x, y);
    }

    // Pauses at each station are built into the loops so the chefs spend time working.
    const team = [
        { trim: "#aa6b47", path: [[150, 238, 4], [228, 238, 3], [349, 238, 4], [150, 238, 0]] },
        { trim: "#466b56", path: [[290, 289, 3], [428, 289, 5], [550, 289, 2], [290, 289, 0]], down: true },
        { trim: "#6c7193", path: [[750, 453, 5], [882, 453, 4], [680, 453, 2], [750, 453, 0]] },
        { trim: "#a54f44", path: [[950, 238, 3], [829, 238, 1], [760, 238, 2], [829, 238, 0], [950, 238, 0]] },
        { trim: "#587d7f", path: [[300, 534, 3], [527, 534, 4], [760, 534, 3], [300, 534, 0]], down: true },
    ];

    function position(path, time) {
        const legs = path.slice(0, -1).map(([x, y, pause], index) => {
            const [nextX, nextY] = path[index + 1];
            return { x, y, pause, dx: nextX - x, dy: nextY - y,
                travel: Math.hypot(nextX - x, nextY - y) / 73 };
        });
        let remaining = time % legs.reduce((sum, leg) => sum + leg.pause + leg.travel, 0);
        for (const leg of legs) {
            if (remaining <= leg.pause) return { x: leg.x, y: leg.y, walking: false };
            remaining -= leg.pause;
            if (remaining <= leg.travel) {
                const fraction = remaining / leg.travel;
                return { x: leg.x + leg.dx * fraction, y: leg.y + leg.dy * fraction,
                    walking: true, angle: Math.atan2(leg.dy, leg.dx) + Math.PI / 2 };
            }
            remaining -= leg.travel;
        }
        return { x: path[0][0], y: path[0][1], walking: false };
    }

    function drawChef(chef, time) {
        const { x, y, walking, angle } = position(chef.path, time);
        const stride = Math.sin(time * (walking ? 14 : 8));
        oval(scene, x + 5, y + 7, 15, 11, "#101815a6");
        scene.save();
        scene.translate(x, y);
        scene.rotate(walking ? angle : chef.down ? Math.PI : 0);
        oval(scene, -7, 9 + stride * 3, 4, 7, "#252b29");
        oval(scene, 7, 9 - stride * 3, 4, 7, "#252b29");
        oval(scene, 0, 2, 13, 10, chef.trim, "#1e2923");
        oval(scene, 0, -5, 9, 8, "#ba855e", "#695443");
        oval(scene, 0, -8, 9, 8, "#fff3dc", "#aa9c82");
        oval(scene, -2, -10, 5, 4, "#fffaf1");
        oval(scene, -13, walking ? stride * 5 : -9, 3, 5, "#e9dfca");
        oval(scene, 13, walking ? -stride * 5 : -9 + stride * 3, 3, 5, "#e9dfca");
        scene.restore();
    }

    function draw(time) {
        scene.drawImage(plan, 0, 0);
        for (const [index, chef] of team.entries()) drawChef(chef, time + index * 2.8);
        for (const [index, x] of [151, 228, 349].entries()) {
            for (let wisp = 0; wisp < 3; wisp++) {
                const rise = (time + index * .37 + wisp * .52) % 1.6 / 1.6;
                oval(scene, x + Math.sin(rise * 8 + wisp) * 7, 140 - rise * 34, 3 + rise * 6,
                    2 + rise * 5, `rgba(239,245,221,${.23 * (1 - rise)})`);
            }
        }
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let paused = false;
    let frame;
    let last = 0;
    let elapsed = 0;
    function tick(now) {
        if (now - last >= 32) {
            elapsed += last ? Math.min(now - last, 100) : 0;
            last = now;
            draw(elapsed / 1000);
        }
        frame = window.requestAnimationFrame(tick);
    }

    function syncMotion() {
        window.cancelAnimationFrame(frame);
        last = 0;
        if (!paused && !reducedMotion.matches && !document.hidden) {
            frame = window.requestAnimationFrame(tick);
        }
        motionButton.hidden = reducedMotion.matches;
        motionButton.textContent = paused ? "Resume motion" : "Pause motion";
    }

    door.addEventListener("click", () => {
        dialog.append(canvas);
        draw(elapsed / 1000);
        dialog.showModal();
        syncMotion();
    });
    dialog.querySelector(".kitchen-exit").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        backdrop.append(canvas);
        syncMotion();
        door.focus({ preventScroll: true });
    });
    motionButton.addEventListener("click", () => {
        paused = !paused;
        syncMotion();
    });
    document.addEventListener("visibilitychange", syncMotion);
    reducedMotion.addEventListener("change", syncMotion);
    draw(0);
    syncMotion();
})();
