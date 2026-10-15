# Survey design, according to the corpus

Source: only the documents in the corpus of the 8 October run (those listed in each run's `manifest.json`). Nothing comes from memory or from the internet. Each item carries the file, the page and the passage that supports it. File names are those in `corpus/documents.csv`. The page is the PDF page (counted from the first sheet of the file), which may not match the printed number. Quotes are verbatim as they come out of the extracted text, with line breaks joined; the hyphenated word breaks of the original are kept. When an item is not in the corpus, the entry says "not found in the corpus".

The sample figures are those each document gives for its own year or design, which is not always that of the edition of the questionnaire assessed; the edition rows of each country table show the distance. Only two countries give the number of persons in the sample in the corpus, and in both cases for a single quarter: Spain (Q2 2023) and the United Kingdom (wave 1, from July–September 2020). Neither gives it per year.

## Summary

| Country | Survey | Periodicity | Sample | Coverage | Lowest representative territorial level (n) | Publication threshold |
|---|---|---|---|---|---|---|
| Argentina | Encuesta Permanente de Hogares (EPH) | Quarterly | 25,000 households per quarter and 100,000 per year (1998 design proposal, cited in 2003); 26,940 dwellings selected in Q2 2020 | Urban: 31 agglomerations | Agglomeration (31); those with fewer than 500,000 inhabitants, only half-yearly and annual | Not found (only design CV targets: 2% national, 5% regional) |
| Bolivia | Encuesta Continua de Empleo (ECE) | Monthly and quarterly | 17,784 dwellings per quarter (1,482 PSUs × 12 dwellings) | National, urban and rural, nine departments | Quarterly: conurbations of La Paz, Santa Cruz and Cochabamba (3) | CV scale: optimal < 10%, good 10–15%, fair 16–20%, not significant > 20% |
| Chile | Encuesta Nacional de Empleo (ENE) | Monthly, in rolling quarters | About 54,000 dwellings (from April–June 2020, with oversample) | National, urban and rural (345 of 346 communes) | Region (16) | n ≥ 60, degrees of freedom ≥ 9; CV ≤ 0.15 acceptable, 0.15–0.30 unreliable, > 0.30 suppressed |
| Colombia | Gran Encuesta Integrada de Hogares (GEIH) | Monthly publication; weekly collection | About 315,000 households per year | National, with exclusions in Amazonia, Orinoquia, Providencia and San Andrés | Department (32 in the list, including Bogotá) | Disaggregations with CV > 15% are not recommended |
| Ecuador | Encuesta Nacional de Empleo, Desempleo y Subempleo (ENEMDU) | Monthly, with quarterly and annual accumulations | 9,016 dwellings per month; 27,048 per quarter; 108,192 per year | National, urban and rural | Province, in the annual accumulation (24) | Not found |
| Spain | Encuesta de Población Activa (EPA) | Quarterly, continuous survey | 5,298 sections × 13 dwellings from Q1 2024 (previously 3,822 × 22); 94,567 persons aged 16 to 74 in the Q2 2023 sample | The whole national territory, family dwellings | Province (number not found in the corpus) | Not found (only "el grado de desagregación que permite el coeficiente de variación") |
| Italy | Rilevazione sulle Forze di Lavoro (RFL) | Quarterly | About 70,000 families per quarter (theoretical sample) | Families resident in Italy | Not found | Not found |
| Mexico | Encuesta Nacional de Ocupación y Empleo (ENOE) | Continuous, weekly fieldwork, quarterly sample | "150 566 mil viviendas cada trimestre" (figure illegible in the extracted text; the dwelling file of Q1 2023 has exactly 150,566 dwellings, see the Mexico note in `COMPARABLE_SAMPLE.md`) | National, by locality size (urban and rural) | Federal entity (number not found) and 39 self-representing cities | Not found |
| Paraguay | Encuesta Permanente de Hogares Continua (EPHC) | Not found in the corpus | Not found in the corpus | Not found in the corpus | Not found in the corpus | Not found in the corpus |
| Peru | Encuesta Nacional de Hogares (ENAHO) | Continuous since 2003; annual and quarterly estimates | 36,594 dwellings in 2024 (24,242 urban, 12,352 rural) | National, urban and rural, 24 departments and Callao | Department, annual (24) | Not found (no numerical threshold) |
| United Kingdom | Labour Force Survey (LFS) | Quarterly | 25,800 new addresses per quarter in Great Britain south of the Caledonian Canal, 80 north of it and 1,300 in Northern Ireland; about 69,000 persons in wave 1 from July–September 2020 | Population resident in private households in the United Kingdom | Not found for the quarterly LFS (the APS gives annual estimates for small areas) | Estimates below 10,000 (about 25 cases, relative error of about 20%): treat with caution |
| Uruguay | Encuesta Continua de Hogares (ECH) | Monthly | About 10,000 households per month (six rotation groups of about 2,000) | National | Not stated explicitly (strata: 19 departments and the metropolitan area) | The INE uses the CV to decide whether to publish ("No publicar si…"), but the cut-offs are not in the extracted text |

## Argentina

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Permanente de Hogares (EPH) | `EPH_nota_metodologica_1_trim_2019.pdf`, p. 1 | "la definición y la cobertura geográfica de los 31 aglomerados incluidos en la Encuesta Permanente de Hogares (EPH)" |
| Edition: dwelling questionnaire | Q2 2002 | `EPHContinua_CuestVivienda.pdf`, p. 1 | "Aplicado a partir del 2° trimestre 2002" |
| Edition: individual questionnaire | Q4 2023 | `EPHContinua_CuestIndividual.pdf`, p. 1 | "Aplicado a partir del cuarto trimestre de 2023" |
| Edition: household questionnaire | Q4 2023 | `EPHContinua_CuestHogar.pdf`, p. 1 | "Aplicado a partir del cuarto trimestre 2023" |
| Edition: methodology | 2003 | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 17 | "INDEC - La nueva Encuesta Permanente de Hogares de Argentina. 2003" |
| Edition: methodological considerations | Q2 2020 | `EPH_consideraciones_metodologicas_2t20.pdf`, p. 5 | "EPH. Consideraciones metodológicas sobre el tratamiento de la información del segundo trimestre de 2020" |
| Edition: methodological note | Q1 2019 | `EPH_nota_metodologica_1_trim_2019.pdf` | from the file name |
| Edition: informality | April 2025 | `metodologia_informalidad_laboral.pdf`, p. 1 | "Metodología INDEC N° 43 Abril de 2025" |
| Periodicity | Quarterly | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 17; `EPH_consideraciones_metodologicas_2t20.pdf`, p. 4 | "La encuesta reformulada tendrá periodicidad trimestral (se darán 4 estimaciones por año)"; "Es una encuesta que brinda información trimestral y se basa en una muestra probabi- lística, estratificada, en dos etapas de selección." |
| Sample (design) | 25,000 households per quarter, 100,000 per year | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 17 | "Pensando en la extensión de la muestra a nivel nacional se propuso un total de 25.000 hogares por trimestre y 100.000 hogares por año (INDEC-EPH, 1998)" |
| Sample (Q2 2020) | 26,940 dwellings selected, 11,841 responded | `EPH_consideraciones_metodologicas_2t20.pdf`, p. 6 | "de las 26.940 vi- viendas seleccionadas para el segundo trimestre de 2020 se consiguió información de contacto para 21.950 y, de ellas, en 11.841 sus habitantes respondieron la encuesta." |
| Sample of persons | not found in the corpus | | |
| Coverage | Urban: agglomerations | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 3 and p. 17 | "se han llegado a cubrir 31 aglomerados urbanos y un área urbano-rural" (on the original survey format); "la encuesta continua se implementara en una primer etapa en los aglomerados urbanos que venían siendo cubiertos por la EPH puntual." |
| Lowest representative level | Agglomeration (quarterly for those with 500,000 inhabitants or more; half-yearly and annual for smaller ones) | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 18 | "se agregarán las muestras trimestrales para dar una estimación semestral a nivel de cada uno de los aglomerados, de los principales indicadores de la Encuesta. Para totales, regiones y aquellos aglomerados para los cuales el tamaño de muestra así lo permita, se darán estimaciones trimestrales." |
| Number of units | 31 agglomerations | `EPH_nota_metodologica_1_trim_2019.pdf`, p. 1 | "la cobertura geográfica de los 31 aglomerados incluidos en la Encuesta Permanente de Hogares (EPH)" |
| Publication threshold | not found in the corpus. There are design precision targets, not publication rules. | `metodologia_eph_continua_2003_sin_anexo2.pdf`, p. 18 | "estimar la tasa nacional de desempleo con un coeficiente de variación inferior al 2% y las tasas por región con un coeficiente de variación del 5%." |

## Bolivia

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Continua de Empleo (ECE) | `NOTA TEC_ECE01_2020.pdf`, p. 1 | "a partir del mes de octubre de la gestión 2015 lleva a cabo en el país la Encuesta Continua de Empleo (ECE)" |
| Edition: questionnaire | Version 9 (reduced), from Q4 2024 | `CUESTIONARIO V9_bol_partir del cuarto trimestre de 2024.pdf`, p. 1 | "VERSION 9 (REDUCIDA)"; the quarter, from the file name |
| Edition: sample design | Version 3.0, no year on the cover | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 1 | "DISEÑO METODOLÓGICO DE LA MUESTRA V3.0 ENCUESTA CONTINUA DE EMPLEO" |
| Edition: technical notes | 17 February, 29 September and 30 October 2020 | `NOTA TEC_ECE01_2020.pdf`, `Nota tecnica_ECE02_2020_trat sesgos.pdf`, `NT_ECE03_2020.pdf`, p. 1 | "Nota técnica: ECE 01/2020 … 17 de febrero de 2020"; "Nota Técnica: ECE 02/2020 … 29 de septiembre de 2020"; "Nota Técnica: ECE 03/2020 … 30 de octubre de 2020" |
| Periodicity | Monthly and quarterly | `NOTA TEC_ECE01_2020.pdf`, p. 1 | "con el objetivo de proporcionar información estadística trimestral y mensual, destinada a reflejar el comportamiento de la desocupación, la oferta y la movilidad de trabajo en el ámbito urbano y rural." |
| Sample | 17,784 dwellings per quarter; 1,482 PSUs per quarter, 12 dwellings per PSU | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 12 | "El tamaño de la muestra para la ECE es de 17784 viviendas por trimestre."; "El número de UPM planificadas para la ECE a diseño final es de 1.482 UPM por cada trimestre, distribuidas en 13 semanas"; "En cada una de las UPM se selecciona 12 viviendas." |
| Sample of households or persons | not found in the corpus | | |
| Coverage | National, urban and rural | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 8 | "La Encuesta Continua de Empleo considera una cobertura geográfica sobre los nueve departamentos y el área urbana y rural." |
| Lowest representative level | Quarterly: conurbations of La Paz, Santa Cruz and Cochabamba; monthly: national | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 17 | "la representatividad de la ECE con periodicidad mensual es Nacional, en el caso de la periodicidad trimestral la representatividad es Total Nacional, Urbano-Rural y conurbaciones de La Paz, Santa Cruz y Cochabamba." Among the objectives (p. 7) it also lists: "Determinar el tamaño de la muestra por departamento (…) los cuales permitan efectuar estimaciones de las variables de interés." |
| Number of units | 3 conurbations | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 17 (same passage as above) | |
| Publication threshold | Quality scale by CV | `DISEÑO DE MUESTRA ECE_v3_BOLIVIA act.pdf`, p. 30 | "Para la ECE, se considera los siguientes estándares para evaluación de los errores muestrales (CV): Optimo: <10% Bueno: 10% a 15% Regular: 16% a 20% **No significativo: >20% **Indicador sujeto a evaluación." |

## Chile

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Nacional de Empleo (ENE) | `metodologia-ene-2020.pdf`, p. 1 | "Documento Metodológico Encuesta Nacional de Empleo (ENE) 2021" |
| Edition: questionnaire | 2020 | `cuestionario-ene-2020.pdf` | from the file name; no year on the cover |
| Edition: methodology | 2021 (the file name says 2020) | `metodologia-ene-2020.pdf`, p. 1 | "Documento Metodológico Encuesta Nacional de Empleo (ENE) 2021" |
| Edition: glossary | 26 September 2025 | `glosario-ene.pdf`, p. 1 | "Fecha de actualización: 26 de septiembre de 2025" |
| Periodicity | Monthly publication of rolling quarters | `metodologia-ene-2020.pdf`, p. 133 | "la información de la ENE se publica el último día hábil de cada mes (…) Si bien los datos se publican mensualmente, las bases contienen información de un trimestre completo, inmediatamente anterior al mes de publicación." |
| Sample | About 54,000 dwellings, with oversample (previously 38,000) | `metodologia-ene-2020.pdf`, p. 67 | "en el trimestre móvil de abril, mayo y junio 2020 (AMJ 2020) la muestra ENE tendrá un nuevo tamaño muestral aproximado de 54.000 viviendas, todas provenientes del nuevo MMV 2017." (note 47: "Incluyendo la sobremuestra"; note 46: "El tamaño muestral del diseño anterior era de 38.000 viviendas y no contemplaba sobremuestra.") |
| Sample of persons | not found in the corpus | | |
| Coverage | National, urban and rural | `metodologia-ene-2020.pdf`, p. 30 | "El nuevo marco muestral cubre 345 comunas de las 346 que conforman el territorio nacional, continental e insular. La comuna que queda excluida corresponde a la Antártica Chilena perteneciente a la región de Magallanes." |
| Lowest representative level | Region (urban area of each region; rural area only in ten regions) | `metodologia-ene-2020.pdf`, p. 48 | "Los dominios de estudio o niveles de estimación, para los que el tamaño muestral de la ENE garantiza estimaciones representativas del parámetro de interés son: nacional, nacional urbano, nacional rural, regional, el área urbana de las 16 regiones y el área rural de las regiones de Coquimbo, Valparaíso, O'Higgins, El Maule, Biobío, La Araucanía, Los Lagos, Metropolitana, Los Ríos y Ñuble." |
| Number of units | 16 regions | `metodologia-ene-2020.pdf`, p. 48 (same passage as above) | |
| Publication threshold | Sample size, degrees of freedom and CV | `metodologia-ene-2020.pdf`, pp. 80–81 | "El umbral de aceptación considera un tamaño muestral mayor o igual a 60 unidades."; "El umbral de aceptación contempla que la estimación evaluada tenga nueve o más grados de libertad."; "𝐶𝑉 ≤ 0,15 → 𝐴𝑐𝑒𝑝𝑡𝑎𝑏𝑙𝑒 (…) 0,15 < 𝐶𝑉 ≤ 0,30 → 𝐸𝑠𝑡𝑖𝑚𝑎𝑐𝑖ó𝑛 𝑝𝑜𝑐𝑜 𝑓𝑖𝑎𝑏𝑙𝑒"; "presenta un coeficiente de variación mayor a 0,30 se debe suprimir la estimación para dicho nivel."; "si estas estimaciones suman más de 50% de las que forman el tabulado, este último no debe ser publicado." For proportions, the criterion is a maximum standard error that depends on p (p. 81). |

## Colombia

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Gran Encuesta Integrada de Hogares (GEIH) | `DSO-GEIH-MET-001-V11.pdf`, p. 1 | "METODOLOGÍA GENERAL GRAN ENCUESTA INTEGRADA DE HOGARES GEIH Jun/2023" |
| Edition: questionnaire | January to December 2024 | `C_Cuestionario_Gran_Encuesta_Integrada_de_Hogares_-_GEIH.pdf`, p. 1 | "Etapas 2401 - 2412. Enero - Diciembre 2024." |
| Edition: collection manual | Version 55, January to December 2025 | `G_Manual_de_recolección_y_conceptos_y_básicos_-_GEIH.pdf`, p. 2 | "CNT-GEIH-MOT-001/ Versión 55 Etapas 2501 - 2512 (Enero – diciembre 2025)" |
| Edition: methodology and methodological sheet | June 2023 | `DSO-GEIH-MET-001-V11.pdf`, p. 1; `DSO-GEIH-FME-001-V11.pdf`, p. 1 | "GEIH Jun/2023"; "FICHA METODOLÓGICA GRAN ENCUESTA INTEGRADA DE HOGARES Jun/2023" |
| Edition: informality | July 2022 | `Nueva_medicion_informalidad.pdf`, p. 1 | "Nueva medición de informalidad laboral Julio 2022" |
| Periodicity | Monthly publication; weekly collection | `DSO-GEIH-FME-001-V11.pdf`, p. 11; `DSO-GEIH-MET-001-V11.pdf`, p. 14 | "Las publicaciones de la GEIH se realizan periódicamente cada fin de mes, con un mes de rezago de resultados con respecto al mes de recolección de la información."; "El período de recolección es semanal para las 32 ciudades capitales de departamento con sus áreas metropolitanas." |
| Sample | About 315,000 households per year | `DSO-GEIH-MET-001-V11.pdf`, p. 2 (also `DSO-GEIH-FME-001-V11.pdf`, p. 4) | "Actualmente, la GEIH cuenta con una muestra anual aproximada de 315.000 hogares a nivel nacional" |
| Sample of persons | not found in the corpus | | |
| Coverage | National, with exclusions | `DSO-GEIH-MET-001-V11.pdf`, p. 13 | "La Gran Encuesta Integrada de Hogares tiene una cobertura nacional. Se excluyen de la cobertura de los departamentos de la Amazonia y la Orinoquia, las cabeceras municipales que no son capitales de departamento, así como los centros poblados y rural disperso. También se excluye la población de Providencia y el centro poblado y rural disperso de San Andrés." |
| Lowest representative level | Department. The periodicity of each level is in a table that does not come out in the extracted text. | `DSO-GEIH-MET-001-V11.pdf`, p. 13; `DSO-GEIH-FME-001-V11.pdf`, p. 9 | "La GEIH tiene cobertura nacional y se han establecido diferentes niveles de desagregación temporal y geográfica. En la siguiente tabla, se presenta la descripción de estos niveles"; the list that follows includes "Departamentos: Bogotá, Cundinamarca, Antioquia, …, Guaviare."; "Los errores relativos (CV) se fijan en 4,7% para cada departamento." |
| Number of units | 32 names in the list of departments (includes Bogotá; San Andrés is not listed) | `DSO-GEIH-MET-001-V11.pdf`, p. 13 | list quoted above |
| Publication threshold | Disaggregations with a CV above 15% are not recommended | `DSO-GEIH-MET-001-V11.pdf`, p. 14 (also `DSO-GEIH-FME-001-V11.pdf`, p. 11) | "No se recomienda usar desagregaciones cuyos indicadores posean coeficientes de variación superiores al 15%." Design precision (p. 10): "error de muestreo relativo trimestral de 5,5% en la tasa de desempleo de las ciudades y de 4,7% anual de la pobreza monetaria en los departamentos" |

## Ecuador

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Nacional de Empleo, Desempleo y Subempleo (ENEMDU) | `M_202605_Metodologia_ENEMDU.pdf`, p. 6 | "La Encuesta Nacional de Empleo, Desempleo y Subempleo tiene la siguiente cobertura" |
| Edition: form | May 2026 | `C_202605_Formulario_ENEMDU.pdf`, p. 1 | "MAYO 2026" |
| Edition: interviewer manual | March 2026 | `202603_Manual_del_encuestador_ENEMDU_Marzo_2026.pdf`, p. 1 | "MARZO 2026" |
| Edition: methodology | May 2026, 2021–2026 scheme | `M_202605_Metodologia_ENEMDU.pdf`, p. 13 | from the file name; the document presents "los aspectos metodológicos de la ENEMDU, bajo el nuevo esquema de mejoras para el periodo 2021-2026." |
| Edition: sample design | Q1 2026 | `M_2026_I_trimestre_Metodologia_de_disenio_muestral.pdf`, p. 1 | "Diseño Muestral ENEMDU TRIMESTRAL Enero - M arzo , 2 0 26" |
| Edition: methods articles | 2015 | `3.%20REM-Empleo_condact.pdf` and `M_4_REM-Actualizacion_metodologica_empleo_informal.pdf`, p. 1 | "Revista de Estadística y Metodologías (2015)- Volumen 1" |
| Periodicity | Monthly, with quarterly and annual accumulations | `M_202605_Metodologia_ENEMDU.pdf`, p. 8 | "A partir del 2021, el INEC presenta resultados de mercado laboral mensuales, y acumulados trimestrales y anuales." |
| Sample | 9,016 dwellings per month; 27,048 per quarter; 108,192 per year | `M_202605_Metodologia_ENEMDU.pdf`, p. 13 | "Tamaño de muestra Mensual: 9.016 viviendas Acumulada Trimestral: 27. 048 viviendas Acumulada Anual: 108.192 viviendas" |
| Sample of persons | not found in the corpus | | |
| Coverage | National, urban and rural | `M_202605_Metodologia_ENEMDU.pdf`, p. 8 | "La ENEMDU mensual cuenta con representatividad a nivel nacional, área (urbana y rural); la ENEMDU acumulada trimestral reporta información a nivel nacional, área y 5 ciudades (Quito, Guayaquil, Cuenca, Ambato y Machala); y la ENEMDU anual, además de las desagregaciones mencionadas, presentará resultados con desagregación provincial." |
| Lowest representative level | Province, in the annual accumulation | `M_2026_I_trimestre_Metodologia_de_disenio_muestral.pdf`, p. 9 | "con representatividad, nacional, urbano, rural, por las cinco ciudades principales y además por las 24 provincias del Ecuador." |
| Number of units | 24 provinces | `M_2026_I_trimestre_Metodologia_de_disenio_muestral.pdf`, p. 9 (same passage as above) | |
| Publication threshold | not found in the corpus (the sample design gives the CV formula, p. 41, but no cut-off) | | |

## Spain

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta de Población Activa (EPA) | `resumetepa21.pdf`, p. 1 | "Encuesta de Población Activa Metodología 2021 Descripción general de la encuesta Madrid, 2021" |
| Edition: questionnaire | 2021 | `epacues21.pdf`, p. 1 | "EPA 2021 (Metodología 2021)" |
| Edition: general description | 2021 | `resumetepa21.pdf`, p. 1 | see above |
| Edition: other M documents | 2021 (2021 changes) and 2023 (comparison with registered unemployment) | `epa_cambios2021.pdf`, `medida_efecto_epa_cambios2021.pdf`, `compa_paro_2023.pdf` | from the file name; `compa_paro_2023.pdf` works with the "SEGUNDO TRIMESTRE DE 2023" (p. 8) |
| Periodicity | Quarterly, continuous survey | `resumetepa21.pdf`, p. 3 | "La EPA es una investigación por muestreo de periodicidad trimestral, dirigida a la población que reside en viviendas familiares del territorio nacional"; "La EPA es una encuesta continua, pues las entrevistas se reparten de manera homogénea a lo largo de las 52 semanas del año." |
| Sample (dwellings) | 3,822 sections × 22 dwellings in 2020; 5,298 sections × 13 dwellings from Q1 2024 | `epa_cambios2021.pdf`, p. 2 | "En 2020 el número de secciones de la muestra de la EPA es de 3.822 con un promedio de 22 viviendas teóricas a encuestar por sección y una vez concluido totalmente el cambio de seccionado (ya en el primer trimestre de 2024) tendremos 5.298 secciones con 13 viviendas a encuestar por sección." |
| Sample (persons) | 94,567 persons aged 16 to 74, Q2 2023 | `compa_paro_2023.pdf`, p. 7 | "En 2023, del total de 94.567 personas de entre 16 y 74 años de la muestra EPA, se ha recuperado el documento identificativo para 93.569 de ellas" |
| Coverage | The whole national territory | `resumetepa21.pdf`, p. 6 | "Desde su inicio (1964) la EPA cubre todo el territorio nacional, salvo Ceuta y Melilla, cuya incorporación no se produjo hasta el 2º trimestre de 1988." |
| Lowest representative level | Province, with the detail the CV allows | `resumetepa21.pdf`, p. 4 | "Para las comunidades autónomas y las provincias se ofrece información sobre las principales características con el grado de desagregación que permite el coeficiente de variación de los estimadores." |
| Number of units | not found in the corpus. The document mentions "las 52 delegaciones provinciales del INE" (p. 8), which are field offices, not estimation domains. | | |
| Publication threshold | not found in the corpus. The precision criteria of the European regulation are mentioned without figures. | `epa_cambios2021.pdf`, p. 2 | "Se establecen nuevos criterios de precisión para las estimaciones de las tasas de paro y de empleo de la población de 15 a 74 años y para la tasa de paro de la misma población por NUTS 2 (comunidades autónomas en el caso de España)." |

## Italy

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Rilevazione sulle Forze di Lavoro (RFL) | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 3 | "La Rilevazione sulle Forze di Lavoro (d'ora in avanti RFL) costituisce dal 1959 la principale fonte informativa sul mercato del lavoro" |
| Edition: questionnaire | Q3 2025, longitudinal microdata file (MFR) | `2025/METADATI/ISTAT_MFR_RCFL_Long3_Questionario_2025_Terzo_trimestre.pdf` | from the file name |
| Edition: methodological note | Q3 2025; longitudinal data from 2021 to 2024 | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 1 | "Dati longitudinali a 3 mesi di distanza: 2021t1-2021t2/2024t1-2024t2" |
| Periodicity | Quarterly | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 3 | "essa fornisce, con periodicità trimestrale, da un lato la stima del numero degli occupati e dei non occupati" |
| Sample | About 70,000 families per quarter (theoretical sample), in four rotation groups of about 18,000 | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 5 | "il campione teorico di famiglie relative a ciascuna occasione di indagine (rilevazione trimestrale) è costituito da circa 70 mila famiglie, suddivise equamente nei quattro gruppi di rotazione costituiti, quindi, ciascuno da circa 18 mila famiglie." |
| Sample of persons | not found in the corpus | | |
| Coverage | Families resident in Italy, excluding institutional households | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 3 | "Tali stime si riferiscono a tutti i componenti delle famiglie residenti in Italia al netto dei membri permanenti delle convivenze (ospizi, brefotrofi, istituti religiosi, caserme, ecc.)" |
| Lowest representative level | not found in the corpus. The note deals with the longitudinal microdata and only warns about small territorial domains. | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 5 | "eventuali risultati ottenuti per sottogruppi di popolazione e/o domini territoriali molto piccoli potrebbero avere un elevato grado di incertezza." |
| Number of units | not found in the corpus | | |
| Publication threshold | not found in the corpus | `2025/METADATI/ISTAT_MFR_RCFL_Long3_NotaMetodologicaIndagine_2025_Terzo_trimestre.pdf`, p. 12 | Only: "Alcuni dei quesiti presenti nei file microdati trasversali non sono presenti nei microdati longitudinali o per motivi di affidabilità statistica dell'informazione" |

## Mexico

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Nacional de Ocupación y Empleo (ENOE) | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 3 | "La Encuesta Nacional de Ocupación y Empleo (ENOE) es un proyecto cuyo objetivo es proporcionar información continua sobre las principales características de la ocupación y el empleo de la población residente en México." |
| Edition: questionnaires | 2023 | `C_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Cuestionario_sociodemográ.pdf` and `C_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Cuestionario_de_Ocupación.pdf`, p. 1 | "CS 2023"; "COE BÁSICO 2023" |
| Edition: interviewer manual | 2023 | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, page footer | "INEGI. Encuesta Nacional de Ocupación y Empleo ENOE. Manual del entrevistador. Edición 2023." |
| M document | The corpus for Mexico has no methodological documentation (M); the design data come from the manual. | | |
| Periodicity | Continuous survey; weekly fieldwork; quarterly sample and rotation | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 16 | "Cobertura temporal Encuesta continua que inició su levantamiento en enero de 2005. Periodo de levantamiento Semanalmente de lunes a domingo, durante todo el año."; "La quinta parte de la muestra que ya cumplió con su ciclo de cinco visitas se reemplaza cada tres meses." |
| Sample | Figure illegible in the extracted text | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 16 | "Tamaño de la muestra 150 566 mil viviendas cada trimestre." (the extracted text runs two numbers together; it has to be read in the PDF. Outside the corpus: the ENOE dwelling file for Q1 2023 has exactly 150,566 dwellings, with and without an interview, which suggests the figure is 150,566; see the Mexico note in `COMPARABLE_SAMPLE.md`) |
| Sample of persons | not found in the corpus | | |
| Coverage | National, by locality size | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 16 | "Nacional • Localidades de 100 mil y más habitantes. • Localidades de 15 mil a 99 mil 999 habitantes. • Localidades de 2 mil 500 a 14 mil 999 habitantes. • Localidades de menos de 2 mil 500 habitantes." |
| Lowest representative level | Federal entity and self-representing cities | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 16 | "Desglose geográfico Entidad federativa Ciudades autorrepresentadas (…) • 39 ciudades del primer trimestre de 2020 a la fecha." |
| Number of units | 39 cities; number of entities not found in the corpus | `G_Encuesta_Nacional_de_Ocupación_y_Empleo_ENOE_Manual_del_entrevistador.pdf`, p. 16 (same passage as above) | |
| Publication threshold | not found in the corpus | | |

## Paraguay

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Permanente de Hogares Continua (EPHC) | `2026/T1/95dc7-Cuestionario_EPHC_ 1er Trim 2026.pdf`, p. 1 | "ENCUESTA PERMANENTE DE HOGARES CONTINUA (EPHC)" |
| Edition: questionnaire | Q1 2026 | `2026/T1/95dc7-Cuestionario_EPHC_ 1er Trim 2026.pdf`, p. 1, and the file name | "1er T" |
| M document | The corpus for Paraguay has only the questionnaire. | | |
| Periodicity | not found in the corpus (the cover sheet has a "TRIMESTRE" field, but no document states the periodicity) | | |
| Sample | not found in the corpus | | |
| Coverage | not found in the corpus | | |
| Lowest representative level and number of units | not found in the corpus | | |
| Publication threshold | not found in the corpus | | |

## Peru

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Nacional de Hogares (ENAHO) | `2024/FichaTecnica.pdf`, p. 1 | "La Encuesta Nacional de Hogares (ENAHO) es la investigación que permite al Instituto Nacional de Estadística e Informática (INEI) desde el año 1995, efectuar el seguimiento de los indicadores sobre las condiciones de vida." |
| Edition: questionnaires | 2024 | `2024/CED-01-100-2024.pdf`, `2024/CED-01-200-2024.pdf`, `2024/CED-01A-500 ENAHO 2024.pdf` | from the file name |
| Edition: technical sheet | 2024 | `2024/FichaTecnica.pdf`, p. 1 | "FICHA TÉCNICA ENCUESTA NACIONAL DE HOGARES 2024" |
| Edition: monetary values | 2024 | `2024/DefinicionValoresMonetariosBasedeDatos.pdf` | from the file's folder |
| Periodicity | Continuous; annual and quarterly estimates | `2024/FichaTecnica.pdf`, p. 2 and p. 6 | "La encuesta es continua desde mayo del 2003. El presente año la encuesta se ejecutará de enero hasta el mes de diciembre 2024."; inference levels "Anual" and "Trimestral". |
| Sample | 36,594 dwellings in 2024 (24,242 urban and 12,352 rural); 5,359 clusters | `2024/FichaTecnica.pdf`, p. 4 and p. 5 | "El tamaño anual de la muestra 2024 es de 36 594 viviendas particulares, correspondiendo 24 242 viviendas al área urbana y 12 352 viviendas al área rural. Asimismo, el tamaño de la muestra panel es de 11 814 viviendas particulares mientras que el tamaño de la muestra no panel es de 24 780 viviendas particulares."; "La muestra de conglomerados en el ámbito nacional es de 5 359, corresponde 3 815 conglomerados al área urbana y 1 544 conglomerados al área rural." |
| Sample of persons | not found in the corpus | | |
| Coverage | National, urban and rural | `2024/FichaTecnica.pdf`, p. 1 | "La encuesta se realiza en el ámbito nacional, en el área urbana y rural, en los 24 departamentos del país y en la Provincia Constitucional del Callao." |
| Lowest representative level | Department (annual); quarterly, only national, urban and rural | `2024/FichaTecnica.pdf`, pp. 5–6 | "La muestra de la encuesta permite obtener estimaciones de las características socio- demográficas de la población para los niveles de inferencia siguientes: a. De la muestra Integrada (panel y no panel) Anual (…) 24 departamentos, cada uno como dominio de estudio (…) Trimestral ✓ Nacional ✓ Urbano Nacional ✓ Rural Nacional" |
| Number of units | 24 departments | `2024/FichaTecnica.pdf`, pp. 5–6 (same passage as above) | |
| Publication threshold | not found in the corpus (no figure) | `2024/FichaTecnica.pdf`, p. 6 | "se podrá producir resultados para diferentes "arreglos" de unidades y su nivel de desagregación dependerá fundamentalmente de la precisión (error de muestreo) con que se estime el dato, y este del tamaño de la muestra para cada caso." |

## United Kingdom

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Labour Force Survey (LFS) | `lfsugvoltcm77238281.pdf`, p. 1 | "Labour Force Survey User Guide – Volume 8: Household and Family Data" |
| Edition: questionnaire | October to December 2025 | `volume2octtodec2025.pdf` | from the file name |
| Edition: user guide, volume 1 | 2024, updated in February 2025 | `volume1main2024updatedfeb25.pdf`, p. 1 | "User Guide VOLUME 1 – LFS BACKGROUND AND METHODOLOGY"; the year, from the file name |
| Edition: user guide, volume 8 | 2003 | `lfsugvoltcm77238281.pdf`, p. 1 | "HOUSEHOLD AND FAMILY DATA 2003" |
| Periodicity | Quarterly | `volume1main2024updatedfeb25.pdf`, p. 4; `lfsugvoltcm77238281.pdf`, p. 3 | "In 1992 the sample in GB was increased to cover 60,000 households every quarter enabling quarterly publication of LFS estimates."; "The LFS has both high frequency (quarterly) and a relatively large sample size" |
| Sample (new addresses per quarter) | 25,800 in Great Britain south of the Caledonian Canal (since January–March 2024), 80 north of the canal, 1,300 in Northern Ireland; each address stays for five quarters | `volume1main2024updatedfeb25.pdf`, pp. 17–19 | "The number of addresses selected from the PAF for Wave 1 each quarter is currently 25,800 since January-March 2024" (p. 18); "Currently 80 addresses are selected for Wave 1 each quarter." (p. 19); "Including this boost a total on 1,300 new addresses are added to the sample each quarter." (p. 17) |
| Sample (persons) | About 69,000 persons in wave 1, from July–September 2020 | `volume1main2024updatedfeb25.pdf`, p. 9 | "the achieved LFS main wave 1 sample covered around 69,000 from July- September 2020 onwards." |
| Coverage | Population resident in private households in the United Kingdom | `volume1main2024updatedfeb25.pdf`, p. 14 | "The LFS relates mainly to the population of the UK resident in private households, with the exception of NHS accommodation and student halls of residence." |
| Lowest representative level | not found in the corpus for the quarterly LFS. For the Annual Population Survey, which is built from part of the LFS plus boosts, the corpus says: | `volume1main2024updatedfeb25.pdf`, p. 23 | "The design of the APS enables production of good-quality, annual estimates for relatively small areas of the United Kingdom on a rolling quarterly basis." |
| Number of units | not found in the corpus | | |
| Publication threshold | Estimates below 10,000: high variability, use with caution (not published before 2005) | `volume1main2024updatedfeb25.pdf`, p. 67; `lfsugvoltcm77238281.pdf`, p. 30 | "Before 2005, quarterly LFS estimates of under 10,000 were not published as they are likely to be unreliable. Although this publication policy changed in 2005 (…) Users are advised that estimates below 10,000 are subject to a high degree of sampling variability and should therefore be treated with caution. The 10,000 threshold equates to a sample size of about 25 and a relative standard error of about 20%."; "Publication threshold Any category where the estimated number of households, (or persons or family units, whichever is the level at which the variable is defined), is less than 10,000, is based on too small a sample to be reliable." |

## Uruguay

| Item | Value | Source | Verbatim quote |
|---|---|---|---|
| Official name | Encuesta Continua de Hogares (ECH) | `Metodologia_ECH_2021.pdf`, p. 1 | "Metodología de la Encuesta Continua de Hogares" |
| Edition: questionnaires | 2024 (implantation and follow-up) | `C_Cuestionario_implantación_2024.pdf`, `C_Cuestionario_seguimiento_2024.pdf` | from the file name |
| Edition: methodology | ECH 2021, published on 23 May 2022 | `Metodologia_ECH_2021.pdf`, p. 1 | "Fecha de Publicación: 23 de Mayo de 2022" |
| Periodicity | Monthly; labour market monthly, income quarterly, poverty half-yearly | `Metodologia_ECH_2021.pdf`, p. 8 and pp. 10–11 | "La ECH es una encuesta multipropósito, con periodicidad mensual, en donde se releva información de las viviendas, hogares y las personas del Uruguay."; "Se publican de forma mensual únicamente indicadores de mercado laboral"; "Se publican de forma trimestral únicamente los indicadores referidos al ingreso"; "Se publican de forma semestral los indicadores de pobreza y desigualdad." |
| Sample | About 10,000 households per month; each rotation group, about 2,000 | `Metodologia_ECH_2021.pdf`, p. 9 | "Cada GR tiene un tamaño de muestra esperado (elegibles respondentes) al momento de la implantación de 2.000 hogares aproximadamente. Esto implicó que una vez operativo el panel rotativo de la ECH (…), la muestra para realizar estimaciones mensuales de mercado de trabajo esté compuesta (teniendo en cuenta la no respuesta) de aproximadamente 10.000 hogares." |
| Sample of persons | not found in the corpus | | |
| Coverage | National | `Metodologia_ECH_2021.pdf`, p. 8 | "Desde el año 2006 la ECH posee cobertura nacional" |
| Lowest representative level | not stated explicitly. The design strata start from the departments, the historical monthly publication breaks down by Montevideo and Interior, and income is published by region. | `Metodologia_ECH_2021.pdf`, p. 15, p. 10 and p. 11 | "El primer nivel es geográfico y corresponde a los diecinueve departamentos del país y a la zona metropolitana."; "el INE siguió proporcionado de forma mensual los indicadores de mercado de trabajo para las mismas aperturas/desagregaciones históricas (e.g. Montevideo e Interior, y sexo)."; "manteniendo los dominios de estimaciones mensuales anteriores (regiones geográficas)" |
| Number of units | not found as an estimation domain (19 departments and the metropolitan area as design strata) | | |
| Publication threshold | The INE uses a CV scale that includes "No publicar", but the numerical cut-offs do not come out in the extracted text (they have to be read in the PDF) | `Metodologia_ECH_2021.pdf`, p. 48 | "El INE utiliza el CV para definir la calidad de una estimación y si la misma es o no lo suficientemente estable para ser publicada. Para evaluar la calidad de la estimaciones respecto a la dimensión precisión y exactitud se emplea la siguiente escala de valoración: Excelente si el / Muy bueno si / Bueno si / Aceptable si / Utilizar con precaución si / No publicar si" |
