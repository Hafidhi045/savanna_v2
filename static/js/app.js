document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .4s";
      el.style.opacity = "0";
    }, 6000);
  });
});
