from sec_pipeline.filing_parser import extract_dimensional_passenger_revenue


def test_aal_uses_undimensioned_legacy_passenger_revenue():
    instance_xml = (
        '<xbrli:context id="total"><xbrli:startDate>2018-04-01</xbrli:startDate>'
        '<xbrli:endDate>2018-06-30</xbrli:endDate></xbrli:context>'
        '<xbrli:context id="travel"><xbrli:startDate>2018-04-01</xbrli:startDate>'
        '<xbrli:endDate>2018-06-30</xbrli:endDate><xbrli:scenario>'
        '<xbrldi:explicitMember dimension="us-gaap:ProductOrServiceAxis">'
        'aal:PassengerTravelMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>'
        '<xbrli:context id="loyalty"><xbrli:startDate>2018-04-01</xbrli:startDate>'
        '<xbrli:endDate>2018-06-30</xbrli:endDate><xbrli:scenario>'
        '<xbrldi:explicitMember dimension="us-gaap:ProductOrServiceAxis">'
        'aal:LoyaltyProgramTravelRedemptionsMember</xbrldi:explicitMember>'
        '</xbrli:scenario></xbrli:context>'
        '<us-gaap:PassengerRevenue contextRef="total">10674000000</us-gaap:PassengerRevenue>'
        '<us-gaap:PassengerRevenue contextRef="travel">9877000000</us-gaap:PassengerRevenue>'
        '<us-gaap:PassengerRevenue contextRef="loyalty">797000000</us-gaap:PassengerRevenue>'
    )

    assert extract_dimensional_passenger_revenue(instance_xml, "AAL", 2018, "Q2") == 10_674_000_000


def test_aal_prefers_current_passenger_member_over_legacy_total():
    instance_xml = (
        '<xbrli:context id="current"><xbrli:startDate>2026-07-01</xbrli:startDate>'
        '<xbrli:endDate>2026-09-30</xbrli:endDate><xbrli:scenario>'
        '<xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">'
        'us-gaap:PassengerMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>'
        '<xbrli:context id="legacy"><xbrli:startDate>2026-07-01</xbrli:startDate>'
        '<xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:context>'
        '<us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax '
        'contextRef="current">14900000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>'
        '<us-gaap:PassengerRevenue contextRef="legacy">13761000000</us-gaap:PassengerRevenue>'
    )

    assert extract_dimensional_passenger_revenue(instance_xml, "AAL", 2026, "Q3") == 14_900_000_000


def test_existing_legacy_dimension_mapping_still_matches():
    instance_xml = (
        '<xbrli:context id="passenger"><xbrli:startDate>2025-04-01</xbrli:startDate>'
        '<xbrli:endDate>2025-06-30</xbrli:endDate><xbrli:scenario>'
        '<xbrldi:explicitMember dimension="us-gaap:ProductOrServiceAxis">'
        'ual:PassengerMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>'
        '<us-gaap:PassengerRevenue contextRef="passenger">'
        '12300000000</us-gaap:PassengerRevenue>'
    )

    assert extract_dimensional_passenger_revenue(instance_xml, "UAL", 2025, "Q2") == 12_300_000_000
