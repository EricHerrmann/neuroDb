"""Tutor epoch — textbook chapter registry and context helpers.

Migration target: src/neurodb/tutor/chapter_registry.py
"""
REGISTRY: dict = {
    "augustine_7e": {
        "display_name": "Neuroscience, 7th ed. — Augustine et al.",
        "chapters": {
            1: {
                "title": "Studying the Nervous System",
                "topics": [
                    "neurons", "glia", "neural circuits", "brain imaging",
                    "model systems", "neuroanatomy overview",
                ],
            },
            2: {
                "title": "Electrical Signals of Nerve Cells",
                "topics": [
                    "resting membrane potential", "action potential",
                    "ion gradients", "Nernst equation", "Goldman equation",
                ],
            },
            3: {
                "title": "Voltage-Dependent Membrane Permeability",
                "topics": [
                    "voltage-gated channels", "sodium channel",
                    "potassium channel", "hodgkin-huxley", "channel gating",
                ],
            },
            4: {
                "title": "Ion Channels and Transporters",
                "topics": [
                    "ion channel structure", "selectivity filter",
                    "ligand-gated channels", "transporters", "pumps",
                ],
            },
            5: {
                "title": "Synaptic Transmission",
                "topics": [
                    "chemical synapse", "neuromuscular junction",
                    "vesicle release", "quantal transmission",
                    "EPSP", "IPSP", "synaptic delay",
                ],
            },
            6: {
                "title": "Neurotransmitters and Their Receptors",
                "topics": [
                    "glutamate", "GABA", "acetylcholine", "dopamine",
                    "serotonin", "norepinephrine", "ionotropic receptors",
                    "metabotropic receptors", "AMPA", "NMDA",
                ],
            },
            7: {
                "title": "Molecular Signaling within Neurons",
                "topics": [
                    "G proteins", "second messengers", "cAMP", "PKA",
                    "calcium signaling", "MAPK", "gene expression",
                ],
            },
            8: {
                "title": "Synaptic Plasticity",
                "topics": [
                    "LTP", "LTD", "Hebbian plasticity", "NMDA receptor",
                    "AMPA trafficking", "CaMKII", "metaplasticity",
                    "homeostatic plasticity",
                ],
            },
            9: {
                "title": "The Somatic Sensory System",
                "topics": [
                    "mechanoreceptors", "somatosensory cortex",
                    "dorsal column-medial lemniscal pathway",
                    "spinothalamic tract", "two-point discrimination",
                    "somatotopy", "receptive fields",
                ],
            },
            10: {
                "title": "Pain",
                "topics": [
                    "nociceptors", "substance P", "spinothalamic tract",
                    "gate control theory", "opioid receptors",
                    "chronic pain", "central sensitization",
                ],
            },
            11: {
                "title": "Vision: The Eye",
                "topics": [
                    "photoreceptors", "rods", "cones", "retina",
                    "phototransduction", "bipolar cells", "ganglion cells",
                    "optic nerve", "lateral geniculate nucleus",
                ],
            },
            12: {
                "title": "Central Visual Pathways",
                "topics": [
                    "retinotopy", "LGN", "V1 laminar organization",
                    "orientation selectivity", "ocular dominance columns",
                    "dorsal stream", "ventral stream",
                    "critical period plasticity", "V4", "MT",
                ],
            },
            13: {
                "title": "The Auditory System",
                "topics": [
                    "cochlea", "hair cells", "tonotopy", "auditory cortex",
                    "inferior colliculus", "sound localization",
                    "interaural time difference",
                ],
            },
            14: {
                "title": "The Vestibular System",
                "topics": [
                    "semicircular canals", "otolith organs", "vestibular nuclei",
                    "VOR", "balance", "spatial orientation",
                ],
            },
            15: {
                "title": "The Chemical Senses",
                "topics": [
                    "olfactory receptor neurons", "olfactory bulb",
                    "taste receptor cells", "gustatory cortex",
                    "pheromones", "olfactory coding",
                ],
            },
        },
    },
}


def lookup_chapter(book_key: str, chapter: int) -> dict | None:
    """Return {title, topics} for a chapter, or None if not found."""
    book = REGISTRY.get(book_key)
    if book is None:
        return None
    return book["chapters"].get(chapter)
