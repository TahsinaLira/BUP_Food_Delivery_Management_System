/* main.js — small helpers used across the site */

// Auto-dismiss flash alerts after 4 seconds.
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(function () {
    document.querySelectorAll('.flash-area .alert').forEach(function (a) {
      try { bootstrap.Alert.getOrCreateInstance(a).close(); } catch (e) {}
    });
  }, 4000);
});

// Star rating picker used on the review page.
function initStarPickers() {
  document.querySelectorAll('.star-picker').forEach(function (picker) {
    var input = picker.querySelector('input[type=hidden]');
    var stars = picker.querySelectorAll('i');
    function paint(val) {
      stars.forEach(function (s) {
        var v = parseInt(s.dataset.val, 10);
        s.className = v <= val ? 'bi bi-star-fill' : 'bi bi-star';
      });
    }
    paint(parseInt(input.value, 10) || 5);
    stars.forEach(function (s) {
      s.addEventListener('click', function () {
        input.value = s.dataset.val;
        paint(parseInt(s.dataset.val, 10));
      });
    });
  });
}
