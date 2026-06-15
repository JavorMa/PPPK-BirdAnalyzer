configfile: "config.yaml"

SPECIES_FILTER = config.get("species_filter", "")

rule all:
    input:
        "output/report.csv",
        "output/report_summary.csv"

rule fetch_taxonomy:
    output:
        touch("output/.taxonomy_done")
    script:
        "scripts/fetch_taxonomy.py"

rule consume_kafka:
    output:
        touch("output/.kafka_done")
    script:
        "scripts/kafka_consumer.py"

rule process_audio:
    input:
        "output/.taxonomy_done"
    output:
        touch("output/.audio_done")
    script:
        "scripts/process_audio.py"

rule generate_report:
    input:
        "output/.audio_done",
        "output/.kafka_done"
    output:
        "output/report.csv",
        "output/report_summary.csv"
    params:
        species_filter = SPECIES_FILTER
    shell:
        "py scripts/generate_report.py {params.species_filter}"