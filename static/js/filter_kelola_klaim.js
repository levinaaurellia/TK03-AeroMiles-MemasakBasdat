document.addEventListener('DOMContentLoaded', function() {
    const filterForm = document.getElementById('filterForm');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const statusSelect = document.getElementById('statusFilter');
    const maskapaiSelect = document.getElementById('maskapaiFilter');

    // Fungsi Utama untuk merakit dan mengirim URL baru
    function applyAllFilters() {
        const startVal = startDateInput.value;
        const endVal = endDateInput.value;
        const statusVal = statusSelect.value;
        const maskapaiVal = maskapaiSelect.value;

        // Kita buat URL Params dari awal (kosong)
        const newParams = new URLSearchParams();

        // 1. Tambahkan Status HANYA jika bukan "semua"
        if (statusVal && statusVal !== 'semua') {
            newParams.set('status', statusVal);
        }

        // 2. Tambahkan Maskapai HANYA jika bukan "semua"
        if (maskapaiVal && maskapaiVal !== 'semua') {
            newParams.set('maskapai', maskapaiVal);
        }

        // 3. Tambahkan Tanggal HANYA jika keduanya valid
        if (startVal && endVal && startVal <= endVal) {
            newParams.set('start_date', startVal);
            newParams.set('end_date', endVal);
        }

        // Bandingkan URL baru dengan URL saat ini di browser (hilangkan tanda '?' di depan)
        const currentQueryString = window.location.search.replace('?', '');
        const newQueryString = newParams.toString();

        // Jika ada perubahan, paksa reload ke URL baru
        if (newQueryString !== currentQueryString) {
            let newUrl = window.location.pathname;
            if (newQueryString) {
                newUrl += '?' + newQueryString;
            }
            window.location.href = newUrl;
        }
    }

    // --- CEGAH SUBMIT BAWAAN HTML (misal user tekan Enter) ---
    filterForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Hentikan HTML bawaan
        applyAllFilters();  // Gunakan logika JS kita
    });

    // --- LISTENER UNTUK SELECT DROPDOWN ---
    statusSelect.addEventListener('change', applyAllFilters);
    maskapaiSelect.addEventListener('change', applyAllFilters);

    // --- LISTENER UNTUK TANGGAL ---
    if (startDateInput.value) endDateInput.min = startDateInput.value;
    if (endDateInput.value) startDateInput.max = endDateInput.value;

    startDateInput.addEventListener('change', function() {
        endDateInput.min = this.value ? this.value : '';
        if (this.value && endDateInput.value && endDateInput.value < this.value) {
            endDateInput.value = '';
        }
        applyAllFilters();
    });

    endDateInput.addEventListener('change', function() {
        startDateInput.max = this.value ? this.value : '';
        applyAllFilters();
    });
});
