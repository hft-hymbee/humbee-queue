REGISTERED_TEMPLATES = {
    "1107176223726577961": {
        "message_type": "PM",
        "content": "Dear Shilpkar,\n" \
            "From the month of {month} till today, a total of {total_bags} Dalmia Cement bags have been recorded in your account, out of which {dsp_bags} bags are of Dalmia DSP Cement. Thank you.\n" \
            "Hoga Yogdaan Ka Samman\n" \
            "HUMBEE"
    }
}


NOT_REGISTERED_TEMPLATES = {
    "1107176224111112846": {
        "message_type": "PM",
        "content": "Dear Shilpkar,\n" \
            "This number is not registered with us. Please contact us using your registered mobile number.\n" \
            "Hoga Yogdaan Ka Samman\n" \
            "HUMBEE"
    }
}


VMN_TEMPLATES = {
    **REGISTERED_TEMPLATES,
    **NOT_REGISTERED_TEMPLATES,
}