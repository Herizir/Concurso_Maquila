const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const toggleSidebar = document.getElementById("toggleSidebar");

if (toggleSidebar) {
    toggleSidebar.addEventListener("click", function () {
        sidebar.classList.toggle("open");
        sidebarBackdrop.classList.toggle("show");
    });
}

if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", function () {
        sidebar.classList.remove("open");
        sidebarBackdrop.classList.remove("show");
    });
}
 