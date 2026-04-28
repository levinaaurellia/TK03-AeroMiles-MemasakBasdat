document.addEventListener('DOMContentLoaded', function () {
    // Cari semua elemen dengan class 'toast'
    var toastElList = [].slice.call(document.querySelectorAll('.toast'))
    
    // Aktifkan dan tampilkan masing-masing toast
    var toastList = toastElList.map(function (toastEl) {
        var toast = new bootstrap.Toast(toastEl)
        toast.show()
        return toast
    })
});