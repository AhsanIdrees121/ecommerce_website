odoo.define('e_website.price_range', function (require) {
'use strict';
    $(document).ready(function () {
        $('.oe_website_sale').on('DOMNodeInserted', function (event) {
            debugger;
            var ev = event.currentTarget.firstElementChild.lastElementChild.firstElementChild;
            if ($(ev).hasClass('breadcrumb')) {
                // Trigger the function when the products are rendered
                console.log('Breadcrumb is present')
            }
        });
//        $('#o_wsale_price_range').on('click', function (ev) {
//        debugger;
//        var inputElement = $(this).find('input[type="range"]');
//        const range = inputElement[0];
//        debugger;
//        const search = $.deparam(window.location.search.substring(1));
//        delete search.min_price;
//        delete search.max_price;
//        debugger;
//        if (parseFloat(range.min) !== range.valueLow) {
//            search['min_price'] = range.valueLow;
//        }
//        if (parseFloat(range.max) !== range.valueHigh) {
//            search['max_price'] = range.valueHigh;
//        }
//        debugger;
//        window.location.search = $.param(search);
//        });
    });
});