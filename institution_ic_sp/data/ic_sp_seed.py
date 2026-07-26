"""
Dados iniciais do Instituto de Criminalística de São Paulo.

Espelha a estrutura do Decreto nº 42.847/1998 e o organograma SPTC (rev. 15),
com códigos NPC/EPC utilizados pela Polícia Científica de SP.

Fontes: Decreto 42.847/1998, Res. SSP-12/2020, Portaria SPTC-85/2020,
organograma SPTC e telefones úteis em policiacientifica.sp.gov.br.
"""

from institution_ic_sp.models import ForensicNucleus, ForensicTeam, Institution

IC_SP_INSTITUTION = {
    "name": (
        "Instituto de Criminalística Dr. Octávio Eduardo de Brito Alvarenga"
    ),
    "acronym": "IC-SP",
    "parent_organization": "Superintendência da Polícia Técnico-Científica",
    "legal_reference": "Decreto nº 42.847, de 09/02/1998",
    "headquarters_city": "São Paulo",
    "is_provisional": True,
}

SPECIALIZED_NUCLEI = [
    ("IC-NAT", "Núcleo de Acidentes de Trânsito", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 10),
    ("IC-NCC", "Núcleo de Crimes Contábeis", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 20),
    ("IC-NCPT", "Núcleo de Crimes Contra o Patrimônio", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 30),
    ("IC-NCPS", "Núcleo de Crimes Contra a Pessoa", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 40),
    ("IC-ND", "Núcleo de Documentoscopia", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 50),
    ("IC-NE", "Núcleo de Engenharia", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 60),
    ("IC-NPE", "Núcleo de Perícias Especiais", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 70),
    ("IC-NIC", "Núcleo de Identificação Criminal", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 80),
    ("IC-NPI", "Núcleo de Perícias de Informática", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE, "São Paulo", 90),
    ("IC-NAI", "Núcleo de Análise Instrumental", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 100),
    ("IC-NB", "Núcleo de Balística", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 110),
    ("IC-NBB", "Núcleo de Biologia e Bioquímica", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 120),
    ("IC-NF", "Núcleo de Física", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 130),
    ("IC-NQ", "Núcleo de Química", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 140),
    ("IC-NEE", "Núcleo de Exames de Entorpecentes", ForensicNucleus.NucleusType.SPECIALIZED, ForensicNucleus.OrganizationalCenter.EXAMS_RESEARCH, "São Paulo", 150),
    ("IC-NAL", "Núcleo de Apoio Logístico", ForensicNucleus.NucleusType.SUPPORT, ForensicNucleus.OrganizationalCenter.LOGISTIC_SUPPORT, "São Paulo", 160),
    ("IC-NAA", "Núcleo de Apoio Administrativo", ForensicNucleus.NucleusType.SUPPORT, ForensicNucleus.OrganizationalCenter.ADMIN_SUPPORT, "São Paulo", 170),
]

FIELD_NUCLEI = [
    (
        "NPC-CAP",
        "Núcleo de Perícias Criminalísticas da Capital e Grande São Paulo",
        ForensicNucleus.NucleusType.FIELD_CAPITAL,
        "São Paulo",
        200,
    ),
    ("NPC-AME", "Núcleo de Perícias Criminalísticas de Americana", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Americana", 210),
    ("NPC-ARB", "Núcleo de Perícias Criminalísticas de Araçatuba", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Araçatuba", 220),
    ("NPC-ARQ", "Núcleo de Perícias Criminalísticas de Araraquara", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Araraquara", 230),
    ("NPC-BAU", "Núcleo de Perícias Criminalísticas de Bauru", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Bauru", 240),
    ("NPC-CPS", "Núcleo de Perícias Criminalísticas de Campinas", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Campinas", 250),
    ("NPC-PPR", "Núcleo de Perícias Criminalísticas de Presidente Prudente", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Presidente Prudente", 260),
    ("NPC-RPR", "Núcleo de Perícias Criminalísticas de Ribeirão Preto", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Ribeirão Preto", 270),
    ("NPC-SAN", "Núcleo de Perícias Criminalísticas de Santos", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Santos", 280),
    ("NPC-SJC", "Núcleo de Perícias Criminalísticas de São José dos Campos", ForensicNucleus.NucleusType.FIELD_INTERIOR, "São José dos Campos", 290),
    ("NPC-SRP", "Núcleo de Perícias Criminalísticas de São José do Rio Preto", ForensicNucleus.NucleusType.FIELD_INTERIOR, "São José do Rio Preto", 300),
    ("NPC-SOR", "Núcleo de Perícias Criminalísticas de Sorocaba", ForensicNucleus.NucleusType.FIELD_INTERIOR, "Sorocaba", 310),
]

# (nucleus_code, code, name, city, is_embedded, sort_order)
CAPITAL_TEAMS = [
    ("NPC-CAP", "EPC-SPC", "Equipe de Perícias Criminalísticas Centro", "São Paulo", False, 10),
    ("NPC-CAP", "EPC-SPN", "Equipe de Perícias Criminalísticas Norte", "São Paulo", False, 20),
    ("NPC-CAP", "EPC-SPS", "Equipe de Perícias Criminalísticas Sul", "São Paulo", False, 30),
    ("NPC-CAP", "EPC-SPL1", "Equipe de Perícias Criminalísticas Leste", "São Paulo", False, 40),
    ("NPC-CAP", "EPC-SPL2", "Equipe de Perícias Criminalísticas São Mateus", "São Paulo", False, 50),
    ("NPC-CAP", "EPC-SPO", "Equipe de Perícias Criminalísticas Oeste", "São Paulo", False, 60),
    ("NPC-CAP", "EPC-HPP", "Equipe de Perícias Criminalísticas DHPP", "São Paulo", True, 70),
    ("NPC-CAP", "EPC-DEIC", "Equipe de Perícias Criminalísticas DEIC", "São Paulo", True, 80),
    ("NPC-CAP", "EPC-DETRAN", "Equipe de Perícias Criminalísticas DETRAN", "São Paulo", True, 90),
    ("NPC-CAP", "EPC-GRU", "Equipe de Perícias Criminalísticas Guarulhos", "Guarulhos", False, 100),
    ("NPC-CAP", "EPC-MCR", "Equipe de Perícias Criminalísticas Mogi das Cruzes", "Mogi das Cruzes", False, 110),
    ("NPC-CAP", "EPC-BRU", "Equipe de Perícias Criminalísticas Barueri", "Barueri", False, 120),
    ("NPC-CAP", "EPC-SAD", "Equipe de Perícias Criminalísticas Santo André", "Santo André", False, 130),
    ("NPC-CAP", "EPC-SBC", "Equipe de Perícias Criminalísticas São Bernardo do Campo", "São Bernardo do Campo", False, 140),
    ("NPC-CAP", "EPC-TSE", "Equipe de Perícias Criminalísticas Taboão da Serra", "Taboão da Serra", False, 150),
    ("NPC-CAP", "EPC-FRO", "Equipe de Perícias Criminalísticas Franco da Rocha", "Franco da Rocha", False, 160),
    ("NPC-CAP", "EPC-SPS2", "Equipe de Perícias Criminalísticas Sul 2", "São Paulo", False, 170),
]

INTERIOR_TEAMS = [
    ("NPC-AME", "EPC-LIM", "Equipe de Perícias Criminalísticas Limeira", "Limeira", False, 10),
    ("NPC-AME", "EPC-PIR", "Equipe de Perícias Criminalísticas Piracicaba", "Piracicaba", False, 20),
    ("NPC-AME", "EPC-RCL", "Equipe de Perícias Criminalísticas Rio Claro", "Rio Claro", False, 30),
    ("NPC-AME", "EPC-SBV", "Equipe de Perícias Criminalísticas São João da Boa Vista", "São João da Boa Vista", False, 40),
    ("NPC-AME", "EPC-MGU", "Equipe de Perícias Criminalísticas Mogi Guaçu", "Mogi Guaçu", False, 50),
    ("NPC-ARB", "EPC-AND", "Equipe de Perícias Criminalísticas Andradina", "Andradina", False, 10),
    ("NPC-ARB", "EPC-PEN", "Equipe de Perícias Criminalísticas Penápolis", "Penápolis", False, 20),
    ("NPC-ARQ", "EPC-JAB", "Equipe de Perícias Criminalísticas Jaboticabal", "Jaboticabal", False, 10),
    ("NPC-ARQ", "EPC-SCA", "Equipe de Perícias Criminalísticas São Carlos", "São Carlos", False, 20),
    ("NPC-BAU", "EPC-JAU", "Equipe de Perícias Criminalísticas Jaú", "Jaú", False, 10),
    ("NPC-BAU", "EPC-LIN", "Equipe de Perícias Criminalísticas Lins", "Lins", False, 20),
    ("NPC-BAU", "EPC-OUR", "Equipe de Perícias Criminalísticas Ourinhos", "Ourinhos", False, 30),
    ("NPC-BAU", "EPC-TUP", "Equipe de Perícias Criminalísticas Tupã", "Tupã", False, 40),
    ("NPC-CPS", "EPC-BPA", "Equipe de Perícias Criminalísticas Bragança Paulista", "Bragança Paulista", False, 10),
    ("NPC-CPS", "EPC-JUN", "Equipe de Perícias Criminalísticas Jundiaí", "Jundiaí", False, 20),
    ("NPC-CPS", "EPC-MAR", "Equipe de Perícias Criminalísticas Marília", "Marília", False, 30),
    ("NPC-PPR", "EPC-ADA", "Equipe de Perícias Criminalísticas Adamantina", "Adamantina", False, 10),
    ("NPC-PPR", "EPC-ASS", "Equipe de Perícias Criminalísticas Assis", "Assis", False, 20),
    ("NPC-PPR", "EPC-DRA", "Equipe de Perícias Criminalísticas Dracena", "Dracena", False, 30),
    ("NPC-PPR", "EPC-PVE", "Equipe de Perícias Criminalísticas Presidente Venceslau", "Presidente Venceslau", False, 40),
    ("NPC-RPR", "EPC-BAR", "Equipe de Perícias Criminalísticas Barretos", "Barretos", False, 10),
    ("NPC-RPR", "EPC-BEB", "Equipe de Perícias Criminalísticas Bebedouro", "Bebedouro", False, 20),
    ("NPC-RPR", "EPC-FRA", "Equipe de Perícias Criminalísticas Franca", "Franca", False, 30),
    ("NPC-RPR", "EPC-ITV", "Equipe de Perícias Criminalísticas Ituverava", "Ituverava", False, 40),
    ("NPC-SAN", "EPC-GJA", "Equipe de Perícias Criminalísticas Guarujá", "Guarujá", False, 10),
    ("NPC-SAN", "EPC-INH", "Equipe de Perícias Criminalísticas Itanhaém", "Itanhaém", False, 20),
    ("NPC-SAN", "EPC-REG", "Equipe de Perícias Criminalísticas Registro", "Registro", False, 30),
    ("NPC-SJC", "EPC-CAR", "Equipe de Perícias Criminalísticas Caraguatatuba", "Caraguatatuba", False, 10),
    ("NPC-SJC", "EPC-CRU", "Equipe de Perícias Criminalísticas Cruzeiro", "Cruzeiro", False, 20),
    ("NPC-SJC", "EPC-GTG", "Equipe de Perícias Criminalísticas Guaratinguetá", "Guaratinguetá", False, 30),
    ("NPC-SJC", "EPC-JAC", "Equipe de Perícias Criminalísticas Jacareí", "Jacareí", False, 40),
    ("NPC-SJC", "EPC-TAU", "Equipe de Perícias Criminalísticas Taubaté", "Taubaté", False, 50),
    ("NPC-SRP", "EPC-CAT", "Equipe de Perícias Criminalísticas Catanduva", "Catanduva", False, 10),
    ("NPC-SRP", "EPC-FER", "Equipe de Perícias Criminalísticas Fernandópolis", "Fernandópolis", False, 20),
    ("NPC-SRP", "EPC-JAL", "Equipe de Perícias Criminalísticas Jales", "Jales", False, 30),
    ("NPC-SRP", "EPC-VOT", "Equipe de Perícias Criminalísticas Votuporanga", "Votuporanga", False, 40),
    ("NPC-SOR", "EPC-AVA", "Equipe de Perícias Criminalísticas Avaré", "Avaré", False, 10),
    ("NPC-SOR", "EPC-BOT", "Equipe de Perícias Criminalísticas Botucatu", "Botucatu", False, 20),
    ("NPC-SOR", "EPC-ITI", "Equipe de Perícias Criminalísticas Itapetininga", "Itapetininga", False, 30),
    ("NPC-SOR", "EPC-IVA", "Equipe de Perícias Criminalísticas Itapeva", "Itapeva", False, 40),
]

SUPPORT_TEAMS = [
    ("IC-NAL", "IC-EFRA", "Equipe de Fotografia e Recursos Audiovisuais", "São Paulo", False, 10),
    ("IC-NAL", "IC-EDT", "Equipe de Desenho e Topografia", "São Paulo", False, 20),
]


def load_ic_sp_institution_data(*, clear_existing=False):
    """
    Popula ou repovoa os dados institucionais do IC-SP.

    Args:
        clear_existing: Quando True, remove registros existentes antes de inserir.

    Returns:
        dict com contagem de registros criados por entidade.
    """
    if clear_existing:
        ForensicTeam.objects.all().delete()
        ForensicNucleus.objects.all().delete()
        Institution.objects.all().delete()

    institution, _ = Institution.objects.get_or_create(
        acronym=IC_SP_INSTITUTION["acronym"],
        defaults=IC_SP_INSTITUTION,
    )

    nucleus_by_code = {}
    nuclei_created = 0

    for code, name, nucleus_type, center, city, sort_order in SPECIALIZED_NUCLEI:
        nucleus, created = ForensicNucleus.objects.get_or_create(
            code=code,
            defaults={
                "institution": institution,
                "name": name,
                "nucleus_type": nucleus_type,
                "organizational_center": center,
                "headquarters_city": city,
                "sort_order": sort_order,
            },
        )
        nucleus_by_code[code] = nucleus
        nuclei_created += int(created)

    for code, name, nucleus_type, city, sort_order in FIELD_NUCLEI:
        nucleus, created = ForensicNucleus.objects.get_or_create(
            code=code,
            defaults={
                "institution": institution,
                "name": name,
                "nucleus_type": nucleus_type,
                "organizational_center": ForensicNucleus.OrganizationalCenter.FORENSIC_EXPERTISE,
                "headquarters_city": city,
                "sort_order": sort_order,
            },
        )
        nucleus_by_code[code] = nucleus
        nuclei_created += int(created)

    teams_created = 0
    all_teams = CAPITAL_TEAMS + INTERIOR_TEAMS + SUPPORT_TEAMS

    for nucleus_code, code, name, city, is_embedded, sort_order in all_teams:
        _, created = ForensicTeam.objects.get_or_create(
            code=code,
            defaults={
                "nucleus": nucleus_by_code[nucleus_code],
                "name": name,
                "headquarters_city": city,
                "is_embedded_unit": is_embedded,
                "sort_order": sort_order,
            },
        )
        teams_created += int(created)

    return {
        "institution": 1 if institution else 0,
        "nuclei_created": nuclei_created,
        "teams_created": teams_created,
    }
