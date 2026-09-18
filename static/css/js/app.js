// ==========================================
// CAMPUS360 JAVASCRIPT
// ==========================================

// ==========================================
// LUCIDE ICONS
// ==========================================

function initializeIcons() {

    if (typeof lucide !== "undefined") {

        lucide.createIcons();

    }

}


// ==========================================
// SCROLL REVEAL
// ==========================================

function initializeScrollReveal() {

    const revealElements =
        document.querySelectorAll(".reveal");


    if (!revealElements.length) {
        return;
    }


    function revealOnScroll() {

        revealElements.forEach((element) => {

            const elementTop =
                element.getBoundingClientRect().top;

            const windowHeight =
                window.innerHeight;


            if (elementTop < windowHeight - 80) {

                element.classList.add("visible");

            }

        });

    }


    window.addEventListener(
        "scroll",
        revealOnScroll
    );


    revealOnScroll();

}


// ==========================================
// MOBILE MENU
// ==========================================

function initializeMobileMenu() {

    const menuButton =
        document.querySelector(".mobile-menu-btn");

    const sidebar =
        document.querySelector(".dashboard-sidebar");


    if (!menuButton || !sidebar) {
        return;
    }


    menuButton.addEventListener(
        "click",
        () => {

            sidebar.classList.toggle(
                "mobile-open"
            );

        }
    );

}


// ==========================================
// CLOSE MOBILE MENU
// ==========================================

function initializeMobileMenuLinks() {

    const sidebarLinks =
        document.querySelectorAll(
            ".dashboard-sidebar a"
        );

    const sidebar =
        document.querySelector(
            ".dashboard-sidebar"
        );


    if (!sidebar) {
        return;
    }


    sidebarLinks.forEach((link) => {

        link.addEventListener(
            "click",
            () => {

                sidebar.classList.remove(
                    "mobile-open"
                );

            }
        );

    });

}


// ==========================================
// FORM SUBMIT PROTECTION
// ==========================================

function initializeFormProtection() {

    const forms =
        document.querySelectorAll(
            "form"
        );


    forms.forEach((form) => {

        form.addEventListener(
            "submit",
            () => {

                const submitButtons =
                    form.querySelectorAll(
                        'button[type="submit"]'
                    );


                submitButtons.forEach(
                    (button) => {

                        if (
                            button.dataset
                                .allowMultiple === "true"
                        ) {
                            return;
                        }


                        button.disabled = true;

                        button.classList.add(
                            "is-submitting"
                        );

                    }
                );

            }
        );

    });

}


// ==========================================
// PAGE INITIALIZATION
// ==========================================

function initializeCampus360() {

    initializeIcons();

    initializeScrollReveal();

    initializeMobileMenu();

    initializeMobileMenuLinks();

    initializeFormProtection();

}


// ==========================================
// START
// ==========================================

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeCampus360
    );

} else {

    initializeCampus360();

}
// ==========================================
// CLUB OPPORTUNITY EDIT
// ==========================================

function toggleOpportunityEdit(opportunityId) {

    const panel = document.getElementById(
        "opportunity-edit-" + opportunityId
    );

    if (!panel) {
        return;
    }

    if (panel.style.display === "none") {

        panel.style.display = "block";

    } else {

        panel.style.display = "none";

    }

    if (typeof lucide !== "undefined") {

        lucide.createIcons();

    }

}