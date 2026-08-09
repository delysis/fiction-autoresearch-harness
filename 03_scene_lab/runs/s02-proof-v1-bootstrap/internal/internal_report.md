# Internal Pipeline Comparison

This unblinded report is intentionally separate from the reader packet.

| Candidate | Pipeline | Words | Mean score | Judges | Eligible | Defects |
|---|---|---:|---:|---:|---|---|
| s02-proof-v1-bootstrap-chat_direct-chat_direct-04-polished | chat_direct | 6453 | 83.70 | 1 | no | repetitive_body_shorthand |
| s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04-polished | hybrid_base_program | 6254 | 83.70 | 1 | no | mindreading_inflation, repetitive_body_shorthand |
| s02-proof-v1-bootstrap-raw_organic-raw_organic-03-polished | raw_organic | 6446 | 89.35 | 1 | no | repetitive_body_shorthand |

## Generation summary

```json
{
  "comparison_version": "s02-compute-comparison.v4.1",
  "selected_for_blind_appraisal": [
    "s02-proof-v1-bootstrap-raw_organic-raw_organic-03-polished",
    "s02-proof-v1-bootstrap-chat_direct-chat_direct-04-polished",
    "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04-polished"
  ],
  "excluded_after_internal_ranking": [],
  "selection_rule": "one accepted winner from each declared primary pipeline (direct instruction, Verbalized Sampling, planned native base); fallback to top three only if a primary mode is absent; identities hidden from reader packet"
}
```

## Diversity and ablations

```json
{
  "base_program_to_instruction": {
    "artifact_mode_labels": [
      "hybrid_base_program"
    ],
    "candidate_count": 4,
    "continuation_repairs": 1,
    "diversity": {
      "candidate_count": 4,
      "corpus": {
        "mean_opening_similarity": 0.052829,
        "mean_self_bleu_proxy": 0.034259,
        "unique_dialogue_acts": 0,
        "unique_event_sequences": 0,
        "unique_strategies": 0
      },
      "literary_style_diagnostics": {
        "cadence_families": {
          "felt_like": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "e.\" Mara felt a wave of gratitude. The acknowledgment of her fatigue felt like a hand on her shoulder, a permission to simply exist without performi",
                "match": "felt like",
                "position": 974
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "e observation was accurate—she *was* fidgeting—but the interpretation felt like a violation. It was as if Livia had reached inside her and rearranged",
                "match": "felt like",
                "position": 3146
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "* tired. But the leap from a tightened shoulder to a \"screaming\" fear felt like a bridge built out of air. \"I'm not afraid,\" Mara replied. \"I'm just",
                "match": "felt like",
                "position": 2509
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "he observation was accurate—Mara *was* bracing—but the interpretation felt like a trespass. It was the subtle shift that defined the evening: Livia h",
                "match": "felt like",
                "position": 1701
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "hat the word was a revelation, but that the timing and the tone of it felt like a precision strike. \"See?\" Livia whispered, her voice triumphant in",
                "match": "felt like",
                "position": 3875
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "expressions were mirrors of Livia’s—an intense, curated empathy that felt like a spotlight. Mara felt a sudden, sharp urge to hide her hands, but th",
                "match": "felt like",
                "position": 2540
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "unreadable, though his eyes were fixed on her with an intensity that felt like a physical weight. Livia noticed the glance instantly. \"There it is,",
                "match": "felt like",
                "position": 4540
              }
            ],
            "mean_hits_per_1000_words": 1.176,
            "repeated_across_batch": true,
            "total_count": 16
          },
          "interpretive_coda": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "ing herself into a corner, her own voice becoming a stranger's, until she realized she no longer knew which version of the truth she was defending. Liv",
                "match": "she realized",
                "position": 5847
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "then the session had to end. Livia opened her mouth to respond, but for the first time, there was a hesitation. She looked at the group, then back at Mara.",
                "match": "for the first time",
                "position": 10412
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "between the two words. She talked about her childhood, about the way she had learned to observe before participating, about the specific nature of her inh",
                "match": "she had learned",
                "position": 5053
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "s of trying to be perfectly clear, she felt herself becoming blurred. She was no longer describing her experience; she was auditioning for Livia's approval,",
                "match": "She was no longer",
                "position": 5430
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "more convoluted as she tried to account for Livia's interpretations. She was no longer speaking to be understood; she was speaking to defend a perimeter tha",
                "match": "She was no longer",
                "position": 5398
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "dismantled in real-time. By the time she paused to catch her breath, Mara realized with a sinking feeling that she no longer knew where her actual feeli",
                "match": "Mara realized",
                "position": 5567
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "more she tried to clarify her position, the more fragmented she felt. She was no longer a person speaking her truth; she was a set of symptoms being analyzed",
                "match": "She was no longer",
                "position": 5343
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "he split\" was beginning to affect the collective energy of the group, Mara realized she no longer knew where her actual feelings ended and Livia's interp",
                "match": "Mara realized",
                "position": 5974
              }
            ],
            "mean_hits_per_1000_words": 2.383875,
            "repeated_across_batch": true,
            "total_count": 33
          },
          "merely": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "the more she felt herself slipping. Every explanation she offered was merely more data for Livia to harvest. Each clarification became a new \"micr",
                "match": "merely",
                "position": 5464
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "It forced Livia to define the boundary of her power. If the \"no\" was merely data, then the \"no\" didn't actually exist; it was just another sympto",
                "match": "merely",
                "position": 10197
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "he entire logic of Fulcrum was predicated on the idea that a ‘no’ was merely a mask for a ‘yes’ that was too afraid to speak. To acknowledge a fin",
                "match": "merely",
                "position": 11070
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "ted, her tone quiet but absolute, “it is not discovering truth. It is merely negotiating a surrender.” The words acted like a release valve. The",
                "match": "merely",
                "position": 13848
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "sion one of genuine concern. \"That isn't the breath of someone who is merely sleepy. It’s the breath of someone who is bracing. You're resisting t",
                "match": "merely",
                "position": 1468
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "e was submitting to Livia's interpretation; if she disagreed, she was merely \"resisting.\" The more she tried to clarify her position, the more fra",
                "match": "merely",
                "position": 5249
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "lignment work, such a category didn't exist. To Livia, every \"no\" was merely a \"yes\" that hadn't been properly decoded yet. To acknowledge Mara’s",
                "match": "merely",
                "position": 11577
              }
            ],
            "mean_hits_per_1000_words": 0.510925,
            "repeated_across_batch": true,
            "total_count": 7
          },
          "not_x_but_y": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "let out a long breath, her shoulders dropping an inch. She felt seen, not as a subject, but as a human being pushed to her limit. \"I just... I feel like I've given everything I have to this session",
                "match": "not as a subject, but as a human being pushed to her limit",
                "position": 1131
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "trying to bleed off the tension because you're holding onto a secret—not necessarily a fact, but a feeling. A refusal to align. You're telling us you're tired, but your body is",
                "match": "not necessarily a fact, but a feeling",
                "position": 2892
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "g control over who gets to define it. You're clinging to your privacy not as a sanctuary, but as a fortress. And that fortress is starting to crumble, isn't it?\" This was the s",
                "match": "not as a sanctuary, but as a fortress",
                "position": 3352
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "like a weight?\" The word *secrecy* hit Mara like a physical blow. It wasn't that the word was inherently true, but it was loaded. It carried a moral weight—a suggestion of shame—that tripped a wire",
                "match": "wasn't that the word was inherently true, but it was loaded",
                "position": 4309
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "lt in her solar plexus—a visceral reaction to the word *isolated*. It wasn't that the word was a revelation, but that the timing and the tone of it felt like a precision strike. \"See?\" Livia whispered, her voice triumphant in its gentleness. \"Y",
                "match": "wasn't that the word was a revelation, but that the timing and the tone of it felt like a precision strike",
                "position": 3797
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "ad been when the session began. Livia’s gaze remained fixed on Mara, not as a person, but as a map to be charted. The silence that followed Mara’s rambling defense was not a void, bu",
                "match": "not as a person, but as a map to be charted",
                "position": 6011
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "austed ears, like a bolt sliding into place. Livia didn’t lock it—she didn't have to—but the gesture signaled a shift in the room's geometry. The circle of students shifted, drawing closer, their faces illumina",
                "match": "didn't have to—but the gesture signaled a shift in the room's geometry",
                "position": 634
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "intensity, as if he were trying to provide a different kind of anchor—not by interpreting her, but by simply witnessing her existence without an agenda. The urge to explain surged again—to tell Livia that the gasp was a",
                "match": "not by interpreting her, but by simply witnessing her existence without an agenda",
                "position": 8156
              }
            ],
            "mean_hits_per_1000_words": 3.3361,
            "repeated_across_batch": true,
            "total_count": 46
          },
          "profound": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "veness. She wasn't looming; she was leaning in, her expression one of profound, shimmering empathy. It was a look Mara had come to recognize as Livi",
                "match": "profound",
                "position": 511
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "not in a way Mara could easily name. They were watching her with the profound, terrifying empathy of people who believed they were witnessing a lib",
                "match": "profound",
                "position": 1334
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "he track. Three seconds. The silence grew heavy, then awkward, then profound. Mara looked at Livia, not with anger or fear, but with a clear, deta",
                "match": "profound",
                "position": 9557
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "\"Your body recognizes the word. You aren't just tired, Mara. You are profoundly lonely in your resistance. And that loneliness is what's blocking the",
                "match": "profoundly",
                "position": 4040
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "ied, but the feeling that accompanied it wasn't frustration. It was a profound sense of safety. Jonah didn't look disappointed. He didn't try to pu",
                "match": "profound",
                "position": 19573
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "own skin. Livia’s voice dropped an octave, moving into a register of profound, almost spiritual intimacy. \"You aren't just resisting the room, Mara",
                "match": "profound",
                "position": 6244
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "moment. Then, a slow, genuine smile spread across his face—a look of profound respect that reached his eyes. He understood. He recognized the bank",
                "match": "profound",
                "position": 18608
              }
            ],
            "mean_hits_per_1000_words": 0.5774,
            "repeated_across_batch": true,
            "total_count": 8
          },
          "quiet": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "lence was different. It was a protective perimeter. He didn't use the quiet to observe her or to bait her into a confession. He simply occupied t",
                "match": "quiet",
                "position": 14651
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "and turned to face her. The moonlight caught the edge of his jaw, the quiet intelligence in his eyes. \"I think the most interesting things about",
                "match": "quiet",
                "position": 15747
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "of the stillness she had cultivated in the gaps between breaths, the quiet space she had discovered when she stopped trying to outrun her own fe",
                "match": "quiet",
                "position": 8356
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "she finally spoke, her voice was no longer thin or defensive. It was quiet, steady, and devoid of the need for approval. “Livia,” Mara said, “I",
                "match": "quiet",
                "position": 10118
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "et quality, a hint of genuine confusion leaking through. \"You've gone quiet. Are you retreating? This is the moment where the resistance usually",
                "match": "quiet",
                "position": 10296
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "ieter.” Mara stood, her legs feeling like water. “I think I need the quiet.” They walked in silence, the midnight air of the compound cool and",
                "match": "quiet",
                "position": 15304
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "e clinical empathy as the others. He was watching her with a focused, quiet intensity, as if he were trying to provide a different kind of anchor",
                "match": "quiet",
                "position": 8080
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "t had been a small thing, a fractional pause she had practiced in the quiet of her own mind, a way to decouple a sensation from the command to re",
                "match": "quiet",
                "position": 8765
              }
            ],
            "mean_hits_per_1000_words": 1.0146,
            "repeated_across_batch": true,
            "total_count": 14
          },
          "simply": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "ment of her fatigue felt like a hand on her shoulder, a permission to simply exist without performing. She let out a long breath, her shoulders dr",
                "match": "simply",
                "position": 1024
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "opped. She didn't answer. She didn't explain. She didn't defend. She simply closed her mouth and let the silence expand. The silence was immedia",
                "match": "simply",
                "position": 8533
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "ng to maintain. You're trying to convince us—and yourself—that you're simply exhausted, but your nervous system is screaming that you're afraid.\"",
                "match": "simply",
                "position": 2219
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "stopped talking. She didn't pull away, and she didn't lean in. She simply ceased the effort of explanation. She let her hands fall slack in her",
                "match": "simply",
                "position": 8622
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "l, the more she realized that any reaction—anger, denial, tears—would simply be incorporated into Livia’s tapestry as further evidence of the \"blo",
                "match": "simply",
                "position": 8064
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "wasn't nodding along with the others, nor was he intervening. He was simply observing, his eyes tracking the movement of the room with a detached",
                "match": "simply",
                "position": 8319
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "ion was instantaneous. Livia didn’t need to ask for confirmation; she simply beamed, her expression one of gentle triumph. \"There it is,\" Livia",
                "match": "simply",
                "position": 7076
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "to provide a different kind of anchor—not by interpreting her, but by simply witnessing her existence without an agenda. The urge to explain surg",
                "match": "simply",
                "position": 8188
              }
            ],
            "mean_hits_per_1000_words": 2.094125,
            "repeated_across_batch": true,
            "total_count": 29
          },
          "sudden": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "were looking at the \"truth\" Livia had extracted from her. Mara felt a sudden, dizzying sense of vertigo. She was being narrated in real-time, her",
                "match": "sudden",
                "position": 7713
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
                "evidence": "Mara jumped slightly. Jonah was standing beside her, his presence a sudden, grounding weight. He wasn't touching her, but he was close enough th",
                "match": "sudden",
                "position": 13714
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "ht—a suggestion of shame—that tripped a wire in her chest. She felt a sudden, sharp constriction in her diaphragm, a momentary hitch in her breath",
                "match": "sudden",
                "position": 4463
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
                "evidence": "nder* landed with a heavy, evocative thud. Mara felt her heart skip—a sudden, erratic flutter in the hollow of her throat. It wasn't because she w",
                "match": "sudden",
                "position": 6804
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "ing the word, watching Mara’s skin. \"You're *isolated*.\" Mara felt a sudden, sharp jolt in her solar plexus—a visceral reaction to the word *isol",
                "match": "sudden",
                "position": 3711
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
                "evidence": "lt more exhausted than ashamed—but the way Livia delivered it, with a sudden, sharp precision, triggered a visceral clash. Mara’s diaphragm tighte",
                "match": "sudden",
                "position": 6968
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "s—an intense, curated empathy that felt like a spotlight. Mara felt a sudden, sharp urge to hide her hands, but the movement only served to valida",
                "match": "sudden",
                "position": 2575
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
                "evidence": "ypassed her intellectual filters and struck a raw nerve, triggering a sudden, involuntary spasm in her chest. Her breath hitched, and a sharp, aud",
                "match": "sudden",
                "position": 6892
              }
            ],
            "mean_hits_per_1000_words": 1.958125,
            "repeated_across_batch": true,
            "total_count": 27
          }
        },
        "candidate_count": 4,
        "heuristic": true,
        "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
        "per_candidate": {
          "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01": {
            "cadence_family_counts": {
              "felt_like": 7,
              "interpretive_coda": 6,
              "merely": 2,
              "not_x_but_y": 11,
              "profound": 1,
              "quiet": 3,
              "simply": 6,
              "sudden": 4
            },
            "cadence_hits_per_1000_words": 11.8765,
            "cadence_total_hits": 40,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 2.8986,
            "mean_dialogue_unigram_cosine": 0.110432,
            "mean_dialogue_vocabulary_overlap": 0.1,
            "possible_explanatory_glosses": 2,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02": {
            "cadence_family_counts": {
              "felt_like": 1,
              "interpretive_coda": 9,
              "merely": 2,
              "not_x_but_y": 10,
              "profound": 3,
              "quiet": 6,
              "simply": 9,
              "sudden": 6
            },
            "cadence_hits_per_1000_words": 13.0905,
            "cadence_total_hits": 46,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 9.8039,
            "mean_dialogue_unigram_cosine": 0.247537,
            "mean_dialogue_vocabulary_overlap": 0.055556,
            "possible_explanatory_glosses": 5,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03": {
            "cadence_family_counts": {
              "felt_like": 3,
              "interpretive_coda": 10,
              "merely": 1,
              "not_x_but_y": 13,
              "profound": 2,
              "quiet": 2,
              "simply": 8,
              "sudden": 8
            },
            "cadence_hits_per_1000_words": 13.081,
            "cadence_total_hits": 47,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 6.5574,
            "mean_dialogue_unigram_cosine": 0.177705,
            "mean_dialogue_vocabulary_overlap": 0.071429,
            "possible_explanatory_glosses": 4,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04": {
            "cadence_family_counts": {
              "felt_like": 5,
              "interpretive_coda": 8,
              "merely": 2,
              "not_x_but_y": 12,
              "profound": 2,
              "quiet": 3,
              "simply": 6,
              "sudden": 9
            },
            "cadence_hits_per_1000_words": 14.1566,
            "cadence_total_hits": 47,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 8.6207,
            "mean_dialogue_unigram_cosine": 0.316228,
            "mean_dialogue_vocabulary_overlap": 0.0,
            "possible_explanatory_glosses": 5,
            "possible_voice_indistinctness": false
          }
        },
        "text_scope": "continuation_text_when_available_otherwise_text"
      },
      "pair_count": 6,
      "pairs": [
        {
          "fivegram_jaccard": 0.017344,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
          "opening_trigram_jaccard": 0.04,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
          "self_bleu_proxy": 0.0379,
          "trigram_jaccard": 0.058457,
          "unigram_jaccard": 0.387516
        },
        {
          "fivegram_jaccard": 0.014775,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
          "opening_trigram_jaccard": 0.035088,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
          "self_bleu_proxy": 0.036006,
          "trigram_jaccard": 0.057237,
          "unigram_jaccard": 0.383571
        },
        {
          "fivegram_jaccard": 0.014907,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
          "opening_trigram_jaccard": 0.072727,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
          "self_bleu_proxy": 0.03288,
          "trigram_jaccard": 0.050853,
          "unigram_jaccard": 0.374021
        },
        {
          "fivegram_jaccard": 0.014605,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
          "opening_trigram_jaccard": 0.026316,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
          "self_bleu_proxy": 0.033101,
          "trigram_jaccard": 0.051597,
          "unigram_jaccard": 0.372881
        },
        {
          "fivegram_jaccard": 0.01322,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
          "opening_trigram_jaccard": 0.098592,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
          "self_bleu_proxy": 0.03171,
          "trigram_jaccard": 0.050199,
          "unigram_jaccard": 0.372212
        },
        {
          "fivegram_jaccard": 0.016512,
          "left": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
          "opening_trigram_jaccard": 0.044248,
          "right": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
          "self_bleu_proxy": 0.033955,
          "trigram_jaccard": 0.051399,
          "unigram_jaccard": 0.355528
        }
      ],
      "per_candidate": {
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01": {
          "diversity_contribution": 0.964404,
          "mean_similarity": 0.035596
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02": {
          "diversity_contribution": 0.965763,
          "mean_similarity": 0.034237
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03": {
          "diversity_contribution": 0.965646,
          "mean_similarity": 0.034354
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04": {
          "diversity_contribution": 0.967152,
          "mean_similarity": 0.032848
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "length_compliant": 4,
    "literary_style": {
      "cadence_families": {
        "felt_like": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "e.\" Mara felt a wave of gratitude. The acknowledgment of her fatigue felt like a hand on her shoulder, a permission to simply exist without performi",
              "match": "felt like",
              "position": 974
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "e observation was accurate—she *was* fidgeting—but the interpretation felt like a violation. It was as if Livia had reached inside her and rearranged",
              "match": "felt like",
              "position": 3146
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "* tired. But the leap from a tightened shoulder to a \"screaming\" fear felt like a bridge built out of air. \"I'm not afraid,\" Mara replied. \"I'm just",
              "match": "felt like",
              "position": 2509
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "he observation was accurate—Mara *was* bracing—but the interpretation felt like a trespass. It was the subtle shift that defined the evening: Livia h",
              "match": "felt like",
              "position": 1701
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "hat the word was a revelation, but that the timing and the tone of it felt like a precision strike. \"See?\" Livia whispered, her voice triumphant in",
              "match": "felt like",
              "position": 3875
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "expressions were mirrors of Livia’s—an intense, curated empathy that felt like a spotlight. Mara felt a sudden, sharp urge to hide her hands, but th",
              "match": "felt like",
              "position": 2540
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "unreadable, though his eyes were fixed on her with an intensity that felt like a physical weight. Livia noticed the glance instantly. \"There it is,",
              "match": "felt like",
              "position": 4540
            }
          ],
          "mean_hits_per_1000_words": 1.176,
          "repeated_across_batch": true,
          "total_count": 16
        },
        "interpretive_coda": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "ing herself into a corner, her own voice becoming a stranger's, until she realized she no longer knew which version of the truth she was defending. Liv",
              "match": "she realized",
              "position": 5847
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "then the session had to end. Livia opened her mouth to respond, but for the first time, there was a hesitation. She looked at the group, then back at Mara.",
              "match": "for the first time",
              "position": 10412
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "between the two words. She talked about her childhood, about the way she had learned to observe before participating, about the specific nature of her inh",
              "match": "she had learned",
              "position": 5053
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "s of trying to be perfectly clear, she felt herself becoming blurred. She was no longer describing her experience; she was auditioning for Livia's approval,",
              "match": "She was no longer",
              "position": 5430
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "more convoluted as she tried to account for Livia's interpretations. She was no longer speaking to be understood; she was speaking to defend a perimeter tha",
              "match": "She was no longer",
              "position": 5398
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "dismantled in real-time. By the time she paused to catch her breath, Mara realized with a sinking feeling that she no longer knew where her actual feeli",
              "match": "Mara realized",
              "position": 5567
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "more she tried to clarify her position, the more fragmented she felt. She was no longer a person speaking her truth; she was a set of symptoms being analyzed",
              "match": "She was no longer",
              "position": 5343
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "he split\" was beginning to affect the collective energy of the group, Mara realized she no longer knew where her actual feelings ended and Livia's interp",
              "match": "Mara realized",
              "position": 5974
            }
          ],
          "mean_hits_per_1000_words": 2.383875,
          "repeated_across_batch": true,
          "total_count": 33
        },
        "merely": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "the more she felt herself slipping. Every explanation she offered was merely more data for Livia to harvest. Each clarification became a new \"micr",
              "match": "merely",
              "position": 5464
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "It forced Livia to define the boundary of her power. If the \"no\" was merely data, then the \"no\" didn't actually exist; it was just another sympto",
              "match": "merely",
              "position": 10197
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "he entire logic of Fulcrum was predicated on the idea that a ‘no’ was merely a mask for a ‘yes’ that was too afraid to speak. To acknowledge a fin",
              "match": "merely",
              "position": 11070
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "ted, her tone quiet but absolute, “it is not discovering truth. It is merely negotiating a surrender.” The words acted like a release valve. The",
              "match": "merely",
              "position": 13848
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "sion one of genuine concern. \"That isn't the breath of someone who is merely sleepy. It’s the breath of someone who is bracing. You're resisting t",
              "match": "merely",
              "position": 1468
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "e was submitting to Livia's interpretation; if she disagreed, she was merely \"resisting.\" The more she tried to clarify her position, the more fra",
              "match": "merely",
              "position": 5249
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "lignment work, such a category didn't exist. To Livia, every \"no\" was merely a \"yes\" that hadn't been properly decoded yet. To acknowledge Mara’s",
              "match": "merely",
              "position": 11577
            }
          ],
          "mean_hits_per_1000_words": 0.510925,
          "repeated_across_batch": true,
          "total_count": 7
        },
        "not_x_but_y": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "let out a long breath, her shoulders dropping an inch. She felt seen, not as a subject, but as a human being pushed to her limit. \"I just... I feel like I've given everything I have to this session",
              "match": "not as a subject, but as a human being pushed to her limit",
              "position": 1131
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "trying to bleed off the tension because you're holding onto a secret—not necessarily a fact, but a feeling. A refusal to align. You're telling us you're tired, but your body is",
              "match": "not necessarily a fact, but a feeling",
              "position": 2892
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "g control over who gets to define it. You're clinging to your privacy not as a sanctuary, but as a fortress. And that fortress is starting to crumble, isn't it?\" This was the s",
              "match": "not as a sanctuary, but as a fortress",
              "position": 3352
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "like a weight?\" The word *secrecy* hit Mara like a physical blow. It wasn't that the word was inherently true, but it was loaded. It carried a moral weight—a suggestion of shame—that tripped a wire",
              "match": "wasn't that the word was inherently true, but it was loaded",
              "position": 4309
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "lt in her solar plexus—a visceral reaction to the word *isolated*. It wasn't that the word was a revelation, but that the timing and the tone of it felt like a precision strike. \"See?\" Livia whispered, her voice triumphant in its gentleness. \"Y",
              "match": "wasn't that the word was a revelation, but that the timing and the tone of it felt like a precision strike",
              "position": 3797
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "ad been when the session began. Livia’s gaze remained fixed on Mara, not as a person, but as a map to be charted. The silence that followed Mara’s rambling defense was not a void, bu",
              "match": "not as a person, but as a map to be charted",
              "position": 6011
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "austed ears, like a bolt sliding into place. Livia didn’t lock it—she didn't have to—but the gesture signaled a shift in the room's geometry. The circle of students shifted, drawing closer, their faces illumina",
              "match": "didn't have to—but the gesture signaled a shift in the room's geometry",
              "position": 634
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "intensity, as if he were trying to provide a different kind of anchor—not by interpreting her, but by simply witnessing her existence without an agenda. The urge to explain surged again—to tell Livia that the gasp was a",
              "match": "not by interpreting her, but by simply witnessing her existence without an agenda",
              "position": 8156
            }
          ],
          "mean_hits_per_1000_words": 3.3361,
          "repeated_across_batch": true,
          "total_count": 46
        },
        "profound": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "veness. She wasn't looming; she was leaning in, her expression one of profound, shimmering empathy. It was a look Mara had come to recognize as Livi",
              "match": "profound",
              "position": 511
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "not in a way Mara could easily name. They were watching her with the profound, terrifying empathy of people who believed they were witnessing a lib",
              "match": "profound",
              "position": 1334
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "he track. Three seconds. The silence grew heavy, then awkward, then profound. Mara looked at Livia, not with anger or fear, but with a clear, deta",
              "match": "profound",
              "position": 9557
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "\"Your body recognizes the word. You aren't just tired, Mara. You are profoundly lonely in your resistance. And that loneliness is what's blocking the",
              "match": "profoundly",
              "position": 4040
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "ied, but the feeling that accompanied it wasn't frustration. It was a profound sense of safety. Jonah didn't look disappointed. He didn't try to pu",
              "match": "profound",
              "position": 19573
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "own skin. Livia’s voice dropped an octave, moving into a register of profound, almost spiritual intimacy. \"You aren't just resisting the room, Mara",
              "match": "profound",
              "position": 6244
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "moment. Then, a slow, genuine smile spread across his face—a look of profound respect that reached his eyes. He understood. He recognized the bank",
              "match": "profound",
              "position": 18608
            }
          ],
          "mean_hits_per_1000_words": 0.5774,
          "repeated_across_batch": true,
          "total_count": 8
        },
        "quiet": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "lence was different. It was a protective perimeter. He didn't use the quiet to observe her or to bait her into a confession. He simply occupied t",
              "match": "quiet",
              "position": 14651
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "and turned to face her. The moonlight caught the edge of his jaw, the quiet intelligence in his eyes. \"I think the most interesting things about",
              "match": "quiet",
              "position": 15747
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "of the stillness she had cultivated in the gaps between breaths, the quiet space she had discovered when she stopped trying to outrun her own fe",
              "match": "quiet",
              "position": 8356
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "she finally spoke, her voice was no longer thin or defensive. It was quiet, steady, and devoid of the need for approval. “Livia,” Mara said, “I",
              "match": "quiet",
              "position": 10118
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "et quality, a hint of genuine confusion leaking through. \"You've gone quiet. Are you retreating? This is the moment where the resistance usually",
              "match": "quiet",
              "position": 10296
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "ieter.” Mara stood, her legs feeling like water. “I think I need the quiet.” They walked in silence, the midnight air of the compound cool and",
              "match": "quiet",
              "position": 15304
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "e clinical empathy as the others. He was watching her with a focused, quiet intensity, as if he were trying to provide a different kind of anchor",
              "match": "quiet",
              "position": 8080
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "t had been a small thing, a fractional pause she had practiced in the quiet of her own mind, a way to decouple a sensation from the command to re",
              "match": "quiet",
              "position": 8765
            }
          ],
          "mean_hits_per_1000_words": 1.0146,
          "repeated_across_batch": true,
          "total_count": 14
        },
        "simply": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "ment of her fatigue felt like a hand on her shoulder, a permission to simply exist without performing. She let out a long breath, her shoulders dr",
              "match": "simply",
              "position": 1024
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "opped. She didn't answer. She didn't explain. She didn't defend. She simply closed her mouth and let the silence expand. The silence was immedia",
              "match": "simply",
              "position": 8533
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "ng to maintain. You're trying to convince us—and yourself—that you're simply exhausted, but your nervous system is screaming that you're afraid.\"",
              "match": "simply",
              "position": 2219
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "stopped talking. She didn't pull away, and she didn't lean in. She simply ceased the effort of explanation. She let her hands fall slack in her",
              "match": "simply",
              "position": 8622
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "l, the more she realized that any reaction—anger, denial, tears—would simply be incorporated into Livia’s tapestry as further evidence of the \"blo",
              "match": "simply",
              "position": 8064
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "wasn't nodding along with the others, nor was he intervening. He was simply observing, his eyes tracking the movement of the room with a detached",
              "match": "simply",
              "position": 8319
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "ion was instantaneous. Livia didn’t need to ask for confirmation; she simply beamed, her expression one of gentle triumph. \"There it is,\" Livia",
              "match": "simply",
              "position": 7076
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "to provide a different kind of anchor—not by interpreting her, but by simply witnessing her existence without an agenda. The urge to explain surg",
              "match": "simply",
              "position": 8188
            }
          ],
          "mean_hits_per_1000_words": 2.094125,
          "repeated_across_batch": true,
          "total_count": 29
        },
        "sudden": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
            "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "were looking at the \"truth\" Livia had extracted from her. Mara felt a sudden, dizzying sense of vertigo. She was being narrated in real-time, her",
              "match": "sudden",
              "position": 7713
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01",
              "evidence": "Mara jumped slightly. Jonah was standing beside her, his presence a sudden, grounding weight. He wasn't touching her, but he was close enough th",
              "match": "sudden",
              "position": 13714
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "ht—a suggestion of shame—that tripped a wire in her chest. She felt a sudden, sharp constriction in her diaphragm, a momentary hitch in her breath",
              "match": "sudden",
              "position": 4463
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02",
              "evidence": "nder* landed with a heavy, evocative thud. Mara felt her heart skip—a sudden, erratic flutter in the hollow of her throat. It wasn't because she w",
              "match": "sudden",
              "position": 6804
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "ing the word, watching Mara’s skin. \"You're *isolated*.\" Mara felt a sudden, sharp jolt in her solar plexus—a visceral reaction to the word *isol",
              "match": "sudden",
              "position": 3711
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03",
              "evidence": "lt more exhausted than ashamed—but the way Livia delivered it, with a sudden, sharp precision, triggered a visceral clash. Mara’s diaphragm tighte",
              "match": "sudden",
              "position": 6968
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "s—an intense, curated empathy that felt like a spotlight. Mara felt a sudden, sharp urge to hide her hands, but the movement only served to valida",
              "match": "sudden",
              "position": 2575
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04",
              "evidence": "ypassed her intellectual filters and struck a raw nerve, triggering a sudden, involuntary spasm in her chest. Her breath hitched, and a sharp, aud",
              "match": "sudden",
              "position": 6892
            }
          ],
          "mean_hits_per_1000_words": 1.958125,
          "repeated_across_batch": true,
          "total_count": 27
        }
      },
      "candidate_count": 4,
      "heuristic": true,
      "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
      "per_candidate": {
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-01": {
          "cadence_family_counts": {
            "felt_like": 7,
            "interpretive_coda": 6,
            "merely": 2,
            "not_x_but_y": 11,
            "profound": 1,
            "quiet": 3,
            "simply": 6,
            "sudden": 4
          },
          "cadence_hits_per_1000_words": 11.8765,
          "cadence_total_hits": 40,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 2.8986,
          "mean_dialogue_unigram_cosine": 0.110432,
          "mean_dialogue_vocabulary_overlap": 0.1,
          "possible_explanatory_glosses": 2,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-02": {
          "cadence_family_counts": {
            "felt_like": 1,
            "interpretive_coda": 9,
            "merely": 2,
            "not_x_but_y": 10,
            "profound": 3,
            "quiet": 6,
            "simply": 9,
            "sudden": 6
          },
          "cadence_hits_per_1000_words": 13.0905,
          "cadence_total_hits": 46,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 9.8039,
          "mean_dialogue_unigram_cosine": 0.247537,
          "mean_dialogue_vocabulary_overlap": 0.055556,
          "possible_explanatory_glosses": 5,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-03": {
          "cadence_family_counts": {
            "felt_like": 3,
            "interpretive_coda": 10,
            "merely": 1,
            "not_x_but_y": 13,
            "profound": 2,
            "quiet": 2,
            "simply": 8,
            "sudden": 8
          },
          "cadence_hits_per_1000_words": 13.081,
          "cadence_total_hits": 47,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 6.5574,
          "mean_dialogue_unigram_cosine": 0.177705,
          "mean_dialogue_vocabulary_overlap": 0.071429,
          "possible_explanatory_glosses": 4,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-hybrid_base_program-hybrid_base_program-04": {
          "cadence_family_counts": {
            "felt_like": 5,
            "interpretive_coda": 8,
            "merely": 2,
            "not_x_but_y": 12,
            "profound": 2,
            "quiet": 3,
            "simply": 6,
            "sudden": 9
          },
          "cadence_hits_per_1000_words": 14.1566,
          "cadence_total_hits": 47,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 8.6207,
          "mean_dialogue_unigram_cosine": 0.316228,
          "mean_dialogue_vocabulary_overlap": 0.0,
          "possible_explanatory_glosses": 5,
          "possible_voice_indistinctness": false
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "local_compressions": 0,
    "word_counts": [
      3368,
      3514,
      3593,
      3320
    ],
    "writer_models": [
      "gemma-4-31b-raw"
    ]
  },
  "chat_direct": {
    "artifact_mode_labels": [
      "chat_direct"
    ],
    "candidate_count": 4,
    "continuation_repairs": 0,
    "diversity": {
      "candidate_count": 4,
      "corpus": {
        "mean_opening_similarity": 0.041365,
        "mean_self_bleu_proxy": 0.037261,
        "unique_dialogue_acts": 0,
        "unique_event_sequences": 0,
        "unique_strategies": 0
      },
      "literary_style_diagnostics": {
        "cadence_families": {
          "felt_like": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "ired, her mind fraying at the edges, and the idea of being “resolved” felt like a physical promise of sleep. She shifted in her chair, her movements",
                "match": "felt like",
                "position": 1176
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "heavy. Around her, the other students watched with an intensity that felt like a collective embrace, though it functioned like a perimeter. “I don’",
                "match": "felt like",
                "position": 1324
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "of grounding she hadn't even noticed. The accuracy of the observation felt like a physical touch, a precision that made it impossible to simply deny.",
                "match": "felt like",
                "position": 1667
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "t. Now, after hours of being mirrored and narrated, those certainties felt like costumes. She began to wonder if Livia was right. Was her desire for",
                "match": "felt like",
                "position": 4780
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "nce, like the sliding of a bolt. For the first hour, the session had felt like an invitation. Livia had guided her through breathing exercises and s",
                "match": "felt like",
                "position": 1387
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "e more explanation that might finally make her legible, but the words felt like ash. She realized with a jolt of horror that she no longer knew which",
                "match": "felt like",
                "position": 6087
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "she leaned in, entering Mara’s personal space with a gentleness that felt like an invitation. \"Tiredness is often the cloak we use to hide a blockag",
                "match": "felt like",
                "position": 1681
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": ". who is left?\" \"That's the ego speaking,\" Livia said, and the words felt like a surgical strike. \"The ego loves the idea of a 'stable self' because",
                "match": "felt like",
                "position": 5120
              }
            ],
            "mean_hits_per_1000_words": 1.8295,
            "repeated_across_batch": true,
            "total_count": 25
          },
          "interpretive_coda": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "e narrative was no longer hers; it was a response to Livia’s prompts. She was no longer describing her life; she was arguing for her sanity. She could see Li",
                "match": "She was no longer",
                "position": 4517
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "oom, and the terrifying realization that the more she spoke, the less she knew who was actually talking. Livia shifted her position, the leather of",
                "match": "she knew",
                "position": 5728
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "ding Livia with more data, more hooks to hang her interpretations on. She was no longer observing the process; she was fueling it. \"See how you're trying to",
                "match": "She was no longer",
                "position": 4176
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "as not a reaction to pressure; it was a revelation of hidden content. She was no longer a person experiencing a complex moment of stress; she was a set of da",
                "match": "She was no longer",
                "position": 7459
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "rify her position, the more blurred the edges of her identity became. She was no longer speaking from a place of conviction; she was pleading for a verdict.",
                "match": "She was no longer",
                "position": 5529
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "ion that might finally make her legible, but the words felt like ash. She realized with a jolt of horror that she no longer knew which version of the st",
                "match": "She realized",
                "position": 6102
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "e mask slipping.\" Mara opened her mouth to respond, but she stopped. She realized with a jolt of horror that she no longer knew which part of her was s",
                "match": "She realized",
                "position": 5416
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "ion to being cornered—had been converted into a spiritual confession. She was no longer a person in pain; she was a data set proving a point. The urge to de",
                "match": "She was no longer",
                "position": 8176
              }
            ],
            "mean_hits_per_1000_words": 1.754,
            "repeated_across_batch": true,
            "total_count": 24
          },
          "merely": {
            "candidate_prevalence": 0.75,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "gentle, melodic cadence that suggested she was not judging Mara, but merely helping her discover the truth of her own heart. “We can’t end the s",
                "match": "merely",
                "position": 640
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "elt like the “bracing” Livia had described. If she disagreed, she was merely proving her resistance. If she agreed, she was admitting to a hidden",
                "match": "merely",
                "position": 2586
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "alize that they had been operating in a world where every refusal was merely a different kind of invitation. Livia opened her mouth to answer, b",
                "match": "merely",
                "position": 12085
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "hich part of her was speaking. Was she defending her soul, or was she merely reacting to the prompts of a master reader? She had offered so many e",
                "match": "merely",
                "position": 5546
              }
            ],
            "mean_hits_per_1000_words": 0.437475,
            "repeated_across_batch": true,
            "total_count": 6
          },
          "not_x_but_y": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "eyes. She spoke with a gentle, melodic cadence that suggested she was not judging Mara, but merely helping her discover the truth of her own heart. “We can’t end the session while you’re still split, Mara,” Livia sa",
                "match": "not judging Mara, but merely helping her discover the truth of her own heart",
                "position": 618
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "a report; it felt like a surrender. It was a loaded prompt, designed not to discover her truth, but to install a new one. Yet, the pressure of the room—the collective, expectant leaning of t",
                "match": "not to discover her truth, but to install a new one",
                "position": 6358
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "be safe?\" The question was a masterstroke. It framed her hesitation not as a boundary, but as a deficiency. To choose safety was to admit to fear; to choose wholeness was to su",
                "match": "not as a boundary, but as a deficiency",
                "position": 2144
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "of the carpet beneath her soles. She reclaimed the space around her, not by pushing against Livia, but by becoming a still point in the center of the room’s orbit. The silence stretched. It moved past the point of being a pause and",
                "match": "not by pushing against Livia, but by becoming a still point in the center of the room’s orbit",
                "position": 8851
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "from the first day's curiosity to the second day's intensity happened not with a crash, but with a gradual, seamless tightening of the atmosphere. By the time the clock hit 1:17 a.m. on her third night, the seminar",
                "match": "not with a crash, but with a gradual, seamless tightening of the atmosphere",
                "position": 85
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "er; they were simply agreeing with Livia’s diagnosis. To disagree was not to offer a different perspective, but to provide further evidence of the \"split\" Livia had identified. Mara felt a sudden, desperate need to be understood. She wanted Liv",
                "match": "not to offer a different perspective, but to provide further evidence of the \"split\" Livia had identified",
                "position": 3273
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "elt increasingly claustrophobic. Around her, the others shifted. They weren't looking at her with judgment, but with a collective, expectant tenderness. It was a circle of care, but as Mara looked at the closed door, she",
                "match": "weren't looking at her with judgment, but with a collective, expectant tenderness",
                "position": 1172
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "h. You’re saying you’re tired, but your body is saying you’re afraid. Not of us—but of the truth that is trying to surface.\" The transition was seamless. Livia had started with a fact—the pos",
                "match": "Not of us—but of the truth that is trying to surface",
                "position": 2193
              }
            ],
            "mean_hits_per_1000_words": 2.76735,
            "repeated_across_batch": true,
            "total_count": 38
          },
          "profound": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "to evoke a sanctuary. Livia sat opposite Mara, her expression one of profound, luminous concern. There was no aggression in her voice, no hardness",
                "match": "profound",
                "position": 463
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": ". She looked at Adrian. He was nodding slowly, his expression one of profound empathy, which only made the situation more suffocating. He wasn't th",
                "match": "profound",
                "position": 8007
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "the room. The other students were watching her with an expression of profound, spiritualized concern. They weren't judging her; they were waiting f",
                "match": "profound",
                "position": 5039
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "nt. But as Mara approached, the irony vanished, replaced by a look of profound, quiet regard. \"I liked the 'final no' part,\" he said. \"Very clean.",
                "match": "profound",
                "position": 15211
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "softened by the amber glow of recessed lighting. The tone was one of profound, gentle care. Everyone spoke in the hushed, reverent cadence of a sup",
                "match": "profound",
                "position": 663
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "ding. He wasn't witnessing. He was watching her with an expression of profound, quiet alertness, his eyes mirroring the very thing Livia claimed she",
                "match": "profound",
                "position": 5822
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "urmur, devoid of aggression. She looked at Mara with an expression of profound, almost maternal concern. \"We can feel the dissonance in the room. It",
                "match": "profound",
                "position": 742
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "op. That isn't the ego disappearing, Mara. That is the sensation of a profound misalignment. You are currently experiencing a spiritual rejection of",
                "match": "profound",
                "position": 6530
              }
            ],
            "mean_hits_per_1000_words": 0.94455,
            "repeated_across_batch": true,
            "total_count": 13
          },
          "quiet": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "ardamom-scented air in her kitchen, and the way she had always felt a quiet distance even among those who loved her. As she spoke, she noticed h",
                "match": "quiet",
                "position": 3966
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "t leaning in. He wasn't analyzing. He was watching her with a steady, quiet intensity, and in his gaze, Mara saw a reflection of herself that was",
                "match": "quiet",
                "position": 8568
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "o Livia was describing. She began to talk about her church, about the quiet expectations of the women she had grown up with, about the way virtue",
                "match": "quiet",
                "position": 3740
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "eir eyes widening. \"There,\" Livia narrated, her voice ringing with a quiet triumph. \"The somatic response. That wasn't a refusal, Mara. That was",
                "match": "quiet",
                "position": 7015
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "asn't witnessing. He was watching her with an expression of profound, quiet alertness, his eyes mirroring the very thing Livia claimed she was hi",
                "match": "quiet",
                "position": 5832
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "nostic sweep, no search for a hidden signal. There was only a steady, quiet recognition of a person who had reached her limit. \"And a practice th",
                "match": "quiet",
                "position": 14075
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "*. There was a flicker of something in his expression—not pity, but a quiet, steady encouragement. It was as if he were reminding her that she di",
                "match": "quiet",
                "position": 8842
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "acle was still standing there, but she was suddenly just a woman in a quiet room, waiting for a signal that was no longer being broadcast. Mara",
                "match": "quiet",
                "position": 10208
              }
            ],
            "mean_hits_per_1000_words": 1.316475,
            "repeated_across_batch": true,
            "total_count": 18
          },
          "simply": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "herself that wasn't fragmented. He wasn't looking for a block; he was simply witnessing a person in distress. In that moment of shared silence,",
                "match": "simply",
                "position": 8697
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "in her chest, nor did she try to smooth it away to please Livia. She simply let it be there. She stopped the flow of explanations, the footnotes,",
                "match": "simply",
                "position": 9023
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "on felt like a physical touch, a precision that made it impossible to simply deny. \"It's just a habit,\" Mara said, but the words sounded thin. \"",
                "match": "simply",
                "position": 1734
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "idn't fight the sensation, and she didn't try to explain it away. She simply let the clash exist. She felt the heat in her cheeks and the tremor i",
                "match": "simply",
                "position": 8009
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "supportive, terrifying certainty. They weren't judging her; they were simply agreeing with Livia’s diagnosis. To disagree was not to offer a diffe",
                "match": "simply",
                "position": 3217
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "silken thread. \"Forget the words. Forget the theology. I want you to simply acknowledge the truth of your attachment. Mara, tell the group: *I am",
                "match": "simply",
                "position": 6621
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "ed way to describe resistance. But why the need to translate? Why not simply exist in the truth of the moment? The fact that you are searching for",
                "match": "simply",
                "position": 3333
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "he students, the humming tension of Livia’s focused attention—and she simply stepped out of it. She didn't pull away or flinch. Instead, she pla",
                "match": "simply",
                "position": 9262
              }
            ],
            "mean_hits_per_1000_words": 2.338175,
            "repeated_across_batch": true,
            "total_count": 32
          },
          "sudden": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": ", that there is something you’ve been told is shameful.” Mara felt a sudden, sharp prickle of panic. She wanted to deny it, but the very act of d",
                "match": "sudden",
                "position": 2433
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
                "evidence": "n, the more you prove that you are hiding.” Mara stopped. She felt a sudden, hollow sensation in her chest. She looked around the room and realiz",
                "match": "sudden",
                "position": 5087
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "nce your present.\" Mara stopped, her mouth slightly open. She felt a sudden, dizzying sense of vertigo. She had started the evening knowing exact",
                "match": "sudden",
                "position": 4555
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
                "evidence": "esire. For a second, Mara felt a violent clash within her own body. A sudden, hot surge of arousal—triggered by the intensity of Livia’s focus and",
                "match": "sudden",
                "position": 6653
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "de further evidence of the \"split\" Livia had identified. Mara felt a sudden, desperate need to be understood. She wanted Livia to see that her he",
                "match": "sudden",
                "position": 3393
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
                "evidence": "hment. Mara, tell the group: *I am afraid to be known.*\" Mara felt a sudden, violent clash in her chest. The phrase wasn't a lie—she was afraid—b",
                "match": "sudden",
                "position": 6733
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "ng to align with the collective frequency of the group?\" Mara felt a sudden, desperate urge to be understood. The warmth of the room, the soft li",
                "match": "sudden",
                "position": 2693
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
                "evidence": "hat, don't you?\" Livia asked, her voice barely above a whisper. \"That sudden, hollow drop. That isn't the ego disappearing, Mara. That is the sens",
                "match": "sudden",
                "position": 6443
              }
            ],
            "mean_hits_per_1000_words": 1.821,
            "repeated_across_batch": true,
            "total_count": 25
          }
        },
        "candidate_count": 4,
        "heuristic": true,
        "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
        "per_candidate": {
          "s02-proof-v1-bootstrap-chat_direct-chat_direct-01": {
            "cadence_family_counts": {
              "felt_like": 8,
              "interpretive_coda": 10,
              "merely": 4,
              "not_x_but_y": 9,
              "profound": 3,
              "quiet": 5,
              "simply": 12,
              "sudden": 6
            },
            "cadence_hits_per_1000_words": 16.745,
            "cadence_total_hits": 57,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 7.6923,
            "mean_dialogue_unigram_cosine": 0.247464,
            "mean_dialogue_vocabulary_overlap": 0.066667,
            "possible_explanatory_glosses": 4,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-chat_direct-chat_direct-02": {
            "cadence_family_counts": {
              "felt_like": 7,
              "interpretive_coda": 5,
              "merely": 0,
              "not_x_but_y": 8,
              "profound": 2,
              "quiet": 5,
              "simply": 7,
              "sudden": 5
            },
            "cadence_hits_per_1000_words": 11.6557,
            "cadence_total_hits": 39,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 3.1746,
            "mean_dialogue_unigram_cosine": 0.533401,
            "mean_dialogue_vocabulary_overlap": 0.083333,
            "possible_explanatory_glosses": 2,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-chat_direct-chat_direct-03": {
            "cadence_family_counts": {
              "felt_like": 4,
              "interpretive_coda": 6,
              "merely": 1,
              "not_x_but_y": 11,
              "profound": 4,
              "quiet": 2,
              "simply": 7,
              "sudden": 5
            },
            "cadence_hits_per_1000_words": 11.4613,
            "cadence_total_hits": 40,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 0.0,
            "mean_dialogue_unigram_cosine": 0.345482,
            "mean_dialogue_vocabulary_overlap": 0.090909,
            "possible_explanatory_glosses": 0,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-chat_direct-chat_direct-04": {
            "cadence_family_counts": {
              "felt_like": 6,
              "interpretive_coda": 3,
              "merely": 1,
              "not_x_but_y": 10,
              "profound": 4,
              "quiet": 6,
              "simply": 6,
              "sudden": 9
            },
            "cadence_hits_per_1000_words": 12.972,
            "cadence_total_hits": 45,
            "comparable_dialogue_speakers": 3,
            "glosses_per_100_dialogue_passages": 4.8387,
            "mean_dialogue_unigram_cosine": 0.408285,
            "mean_dialogue_vocabulary_overlap": 0.095726,
            "possible_explanatory_glosses": 3,
            "possible_voice_indistinctness": false
          }
        },
        "text_scope": "continuation_text_when_available_otherwise_text"
      },
      "pair_count": 6,
      "pairs": [
        {
          "fivegram_jaccard": 0.017406,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
          "opening_trigram_jaccard": 0.021645,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
          "self_bleu_proxy": 0.039419,
          "trigram_jaccard": 0.061432,
          "unigram_jaccard": 0.384043
        },
        {
          "fivegram_jaccard": 0.018389,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
          "opening_trigram_jaccard": 0.035088,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
          "self_bleu_proxy": 0.041494,
          "trigram_jaccard": 0.064599,
          "unigram_jaccard": 0.375738
        },
        {
          "fivegram_jaccard": 0.01362,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
          "opening_trigram_jaccard": 0.044248,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
          "self_bleu_proxy": 0.031683,
          "trigram_jaccard": 0.049746,
          "unigram_jaccard": 0.363397
        },
        {
          "fivegram_jaccard": 0.015194,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
          "opening_trigram_jaccard": 0.067873,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
          "self_bleu_proxy": 0.036164,
          "trigram_jaccard": 0.057134,
          "unigram_jaccard": 0.379648
        },
        {
          "fivegram_jaccard": 0.011763,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
          "opening_trigram_jaccard": 0.035088,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
          "self_bleu_proxy": 0.031326,
          "trigram_jaccard": 0.050888,
          "unigram_jaccard": 0.377309
        },
        {
          "fivegram_jaccard": 0.022091,
          "left": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
          "opening_trigram_jaccard": 0.044248,
          "right": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
          "self_bleu_proxy": 0.043482,
          "trigram_jaccard": 0.064873,
          "unigram_jaccard": 0.391672
        }
      ],
      "per_candidate": {
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-01": {
          "diversity_contribution": 0.962468,
          "mean_similarity": 0.037532
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-02": {
          "diversity_contribution": 0.964364,
          "mean_similarity": 0.035636
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-03": {
          "diversity_contribution": 0.95962,
          "mean_similarity": 0.04038
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-04": {
          "diversity_contribution": 0.964503,
          "mean_similarity": 0.035497
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "length_compliant": 4,
    "literary_style": {
      "cadence_families": {
        "felt_like": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "ired, her mind fraying at the edges, and the idea of being “resolved” felt like a physical promise of sleep. She shifted in her chair, her movements",
              "match": "felt like",
              "position": 1176
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "heavy. Around her, the other students watched with an intensity that felt like a collective embrace, though it functioned like a perimeter. “I don’",
              "match": "felt like",
              "position": 1324
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "of grounding she hadn't even noticed. The accuracy of the observation felt like a physical touch, a precision that made it impossible to simply deny.",
              "match": "felt like",
              "position": 1667
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "t. Now, after hours of being mirrored and narrated, those certainties felt like costumes. She began to wonder if Livia was right. Was her desire for",
              "match": "felt like",
              "position": 4780
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "nce, like the sliding of a bolt. For the first hour, the session had felt like an invitation. Livia had guided her through breathing exercises and s",
              "match": "felt like",
              "position": 1387
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "e more explanation that might finally make her legible, but the words felt like ash. She realized with a jolt of horror that she no longer knew which",
              "match": "felt like",
              "position": 6087
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "she leaned in, entering Mara’s personal space with a gentleness that felt like an invitation. \"Tiredness is often the cloak we use to hide a blockag",
              "match": "felt like",
              "position": 1681
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": ". who is left?\" \"That's the ego speaking,\" Livia said, and the words felt like a surgical strike. \"The ego loves the idea of a 'stable self' because",
              "match": "felt like",
              "position": 5120
            }
          ],
          "mean_hits_per_1000_words": 1.8295,
          "repeated_across_batch": true,
          "total_count": 25
        },
        "interpretive_coda": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "e narrative was no longer hers; it was a response to Livia’s prompts. She was no longer describing her life; she was arguing for her sanity. She could see Li",
              "match": "She was no longer",
              "position": 4517
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "oom, and the terrifying realization that the more she spoke, the less she knew who was actually talking. Livia shifted her position, the leather of",
              "match": "she knew",
              "position": 5728
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "ding Livia with more data, more hooks to hang her interpretations on. She was no longer observing the process; she was fueling it. \"See how you're trying to",
              "match": "She was no longer",
              "position": 4176
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "as not a reaction to pressure; it was a revelation of hidden content. She was no longer a person experiencing a complex moment of stress; she was a set of da",
              "match": "She was no longer",
              "position": 7459
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "rify her position, the more blurred the edges of her identity became. She was no longer speaking from a place of conviction; she was pleading for a verdict.",
              "match": "She was no longer",
              "position": 5529
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "ion that might finally make her legible, but the words felt like ash. She realized with a jolt of horror that she no longer knew which version of the st",
              "match": "She realized",
              "position": 6102
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "e mask slipping.\" Mara opened her mouth to respond, but she stopped. She realized with a jolt of horror that she no longer knew which part of her was s",
              "match": "She realized",
              "position": 5416
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "ion to being cornered—had been converted into a spiritual confession. She was no longer a person in pain; she was a data set proving a point. The urge to de",
              "match": "She was no longer",
              "position": 8176
            }
          ],
          "mean_hits_per_1000_words": 1.754,
          "repeated_across_batch": true,
          "total_count": 24
        },
        "merely": {
          "candidate_prevalence": 0.75,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "gentle, melodic cadence that suggested she was not judging Mara, but merely helping her discover the truth of her own heart. “We can’t end the s",
              "match": "merely",
              "position": 640
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "elt like the “bracing” Livia had described. If she disagreed, she was merely proving her resistance. If she agreed, she was admitting to a hidden",
              "match": "merely",
              "position": 2586
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "alize that they had been operating in a world where every refusal was merely a different kind of invitation. Livia opened her mouth to answer, b",
              "match": "merely",
              "position": 12085
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "hich part of her was speaking. Was she defending her soul, or was she merely reacting to the prompts of a master reader? She had offered so many e",
              "match": "merely",
              "position": 5546
            }
          ],
          "mean_hits_per_1000_words": 0.437475,
          "repeated_across_batch": true,
          "total_count": 6
        },
        "not_x_but_y": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "eyes. She spoke with a gentle, melodic cadence that suggested she was not judging Mara, but merely helping her discover the truth of her own heart. “We can’t end the session while you’re still split, Mara,” Livia sa",
              "match": "not judging Mara, but merely helping her discover the truth of her own heart",
              "position": 618
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "a report; it felt like a surrender. It was a loaded prompt, designed not to discover her truth, but to install a new one. Yet, the pressure of the room—the collective, expectant leaning of t",
              "match": "not to discover her truth, but to install a new one",
              "position": 6358
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "be safe?\" The question was a masterstroke. It framed her hesitation not as a boundary, but as a deficiency. To choose safety was to admit to fear; to choose wholeness was to su",
              "match": "not as a boundary, but as a deficiency",
              "position": 2144
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "of the carpet beneath her soles. She reclaimed the space around her, not by pushing against Livia, but by becoming a still point in the center of the room’s orbit. The silence stretched. It moved past the point of being a pause and",
              "match": "not by pushing against Livia, but by becoming a still point in the center of the room’s orbit",
              "position": 8851
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "from the first day's curiosity to the second day's intensity happened not with a crash, but with a gradual, seamless tightening of the atmosphere. By the time the clock hit 1:17 a.m. on her third night, the seminar",
              "match": "not with a crash, but with a gradual, seamless tightening of the atmosphere",
              "position": 85
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "er; they were simply agreeing with Livia’s diagnosis. To disagree was not to offer a different perspective, but to provide further evidence of the \"split\" Livia had identified. Mara felt a sudden, desperate need to be understood. She wanted Liv",
              "match": "not to offer a different perspective, but to provide further evidence of the \"split\" Livia had identified",
              "position": 3273
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "elt increasingly claustrophobic. Around her, the others shifted. They weren't looking at her with judgment, but with a collective, expectant tenderness. It was a circle of care, but as Mara looked at the closed door, she",
              "match": "weren't looking at her with judgment, but with a collective, expectant tenderness",
              "position": 1172
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "h. You’re saying you’re tired, but your body is saying you’re afraid. Not of us—but of the truth that is trying to surface.\" The transition was seamless. Livia had started with a fact—the pos",
              "match": "Not of us—but of the truth that is trying to surface",
              "position": 2193
            }
          ],
          "mean_hits_per_1000_words": 2.76735,
          "repeated_across_batch": true,
          "total_count": 38
        },
        "profound": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "to evoke a sanctuary. Livia sat opposite Mara, her expression one of profound, luminous concern. There was no aggression in her voice, no hardness",
              "match": "profound",
              "position": 463
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": ". She looked at Adrian. He was nodding slowly, his expression one of profound empathy, which only made the situation more suffocating. He wasn't th",
              "match": "profound",
              "position": 8007
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "the room. The other students were watching her with an expression of profound, spiritualized concern. They weren't judging her; they were waiting f",
              "match": "profound",
              "position": 5039
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "nt. But as Mara approached, the irony vanished, replaced by a look of profound, quiet regard. \"I liked the 'final no' part,\" he said. \"Very clean.",
              "match": "profound",
              "position": 15211
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "softened by the amber glow of recessed lighting. The tone was one of profound, gentle care. Everyone spoke in the hushed, reverent cadence of a sup",
              "match": "profound",
              "position": 663
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "ding. He wasn't witnessing. He was watching her with an expression of profound, quiet alertness, his eyes mirroring the very thing Livia claimed she",
              "match": "profound",
              "position": 5822
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "urmur, devoid of aggression. She looked at Mara with an expression of profound, almost maternal concern. \"We can feel the dissonance in the room. It",
              "match": "profound",
              "position": 742
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "op. That isn't the ego disappearing, Mara. That is the sensation of a profound misalignment. You are currently experiencing a spiritual rejection of",
              "match": "profound",
              "position": 6530
            }
          ],
          "mean_hits_per_1000_words": 0.94455,
          "repeated_across_batch": true,
          "total_count": 13
        },
        "quiet": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "ardamom-scented air in her kitchen, and the way she had always felt a quiet distance even among those who loved her. As she spoke, she noticed h",
              "match": "quiet",
              "position": 3966
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "t leaning in. He wasn't analyzing. He was watching her with a steady, quiet intensity, and in his gaze, Mara saw a reflection of herself that was",
              "match": "quiet",
              "position": 8568
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "o Livia was describing. She began to talk about her church, about the quiet expectations of the women she had grown up with, about the way virtue",
              "match": "quiet",
              "position": 3740
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "eir eyes widening. \"There,\" Livia narrated, her voice ringing with a quiet triumph. \"The somatic response. That wasn't a refusal, Mara. That was",
              "match": "quiet",
              "position": 7015
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "asn't witnessing. He was watching her with an expression of profound, quiet alertness, his eyes mirroring the very thing Livia claimed she was hi",
              "match": "quiet",
              "position": 5832
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "nostic sweep, no search for a hidden signal. There was only a steady, quiet recognition of a person who had reached her limit. \"And a practice th",
              "match": "quiet",
              "position": 14075
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "*. There was a flicker of something in his expression—not pity, but a quiet, steady encouragement. It was as if he were reminding her that she di",
              "match": "quiet",
              "position": 8842
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "acle was still standing there, but she was suddenly just a woman in a quiet room, waiting for a signal that was no longer being broadcast. Mara",
              "match": "quiet",
              "position": 10208
            }
          ],
          "mean_hits_per_1000_words": 1.316475,
          "repeated_across_batch": true,
          "total_count": 18
        },
        "simply": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "herself that wasn't fragmented. He wasn't looking for a block; he was simply witnessing a person in distress. In that moment of shared silence,",
              "match": "simply",
              "position": 8697
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "in her chest, nor did she try to smooth it away to please Livia. She simply let it be there. She stopped the flow of explanations, the footnotes,",
              "match": "simply",
              "position": 9023
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "on felt like a physical touch, a precision that made it impossible to simply deny. \"It's just a habit,\" Mara said, but the words sounded thin. \"",
              "match": "simply",
              "position": 1734
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "idn't fight the sensation, and she didn't try to explain it away. She simply let the clash exist. She felt the heat in her cheeks and the tremor i",
              "match": "simply",
              "position": 8009
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "supportive, terrifying certainty. They weren't judging her; they were simply agreeing with Livia’s diagnosis. To disagree was not to offer a diffe",
              "match": "simply",
              "position": 3217
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "silken thread. \"Forget the words. Forget the theology. I want you to simply acknowledge the truth of your attachment. Mara, tell the group: *I am",
              "match": "simply",
              "position": 6621
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "ed way to describe resistance. But why the need to translate? Why not simply exist in the truth of the moment? The fact that you are searching for",
              "match": "simply",
              "position": 3333
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "he students, the humming tension of Livia’s focused attention—and she simply stepped out of it. She didn't pull away or flinch. Instead, she pla",
              "match": "simply",
              "position": 9262
            }
          ],
          "mean_hits_per_1000_words": 2.338175,
          "repeated_across_batch": true,
          "total_count": 32
        },
        "sudden": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
            "s02-proof-v1-bootstrap-chat_direct-chat_direct-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": ", that there is something you’ve been told is shameful.” Mara felt a sudden, sharp prickle of panic. She wanted to deny it, but the very act of d",
              "match": "sudden",
              "position": 2433
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-01",
              "evidence": "n, the more you prove that you are hiding.” Mara stopped. She felt a sudden, hollow sensation in her chest. She looked around the room and realiz",
              "match": "sudden",
              "position": 5087
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "nce your present.\" Mara stopped, her mouth slightly open. She felt a sudden, dizzying sense of vertigo. She had started the evening knowing exact",
              "match": "sudden",
              "position": 4555
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-02",
              "evidence": "esire. For a second, Mara felt a violent clash within her own body. A sudden, hot surge of arousal—triggered by the intensity of Livia’s focus and",
              "match": "sudden",
              "position": 6653
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "de further evidence of the \"split\" Livia had identified. Mara felt a sudden, desperate need to be understood. She wanted Livia to see that her he",
              "match": "sudden",
              "position": 3393
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-03",
              "evidence": "hment. Mara, tell the group: *I am afraid to be known.*\" Mara felt a sudden, violent clash in her chest. The phrase wasn't a lie—she was afraid—b",
              "match": "sudden",
              "position": 6733
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "ng to align with the collective frequency of the group?\" Mara felt a sudden, desperate urge to be understood. The warmth of the room, the soft li",
              "match": "sudden",
              "position": 2693
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-chat_direct-chat_direct-04",
              "evidence": "hat, don't you?\" Livia asked, her voice barely above a whisper. \"That sudden, hollow drop. That isn't the ego disappearing, Mara. That is the sens",
              "match": "sudden",
              "position": 6443
            }
          ],
          "mean_hits_per_1000_words": 1.821,
          "repeated_across_batch": true,
          "total_count": 25
        }
      },
      "candidate_count": 4,
      "heuristic": true,
      "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
      "per_candidate": {
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-01": {
          "cadence_family_counts": {
            "felt_like": 8,
            "interpretive_coda": 10,
            "merely": 4,
            "not_x_but_y": 9,
            "profound": 3,
            "quiet": 5,
            "simply": 12,
            "sudden": 6
          },
          "cadence_hits_per_1000_words": 16.745,
          "cadence_total_hits": 57,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 7.6923,
          "mean_dialogue_unigram_cosine": 0.247464,
          "mean_dialogue_vocabulary_overlap": 0.066667,
          "possible_explanatory_glosses": 4,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-02": {
          "cadence_family_counts": {
            "felt_like": 7,
            "interpretive_coda": 5,
            "merely": 0,
            "not_x_but_y": 8,
            "profound": 2,
            "quiet": 5,
            "simply": 7,
            "sudden": 5
          },
          "cadence_hits_per_1000_words": 11.6557,
          "cadence_total_hits": 39,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 3.1746,
          "mean_dialogue_unigram_cosine": 0.533401,
          "mean_dialogue_vocabulary_overlap": 0.083333,
          "possible_explanatory_glosses": 2,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-03": {
          "cadence_family_counts": {
            "felt_like": 4,
            "interpretive_coda": 6,
            "merely": 1,
            "not_x_but_y": 11,
            "profound": 4,
            "quiet": 2,
            "simply": 7,
            "sudden": 5
          },
          "cadence_hits_per_1000_words": 11.4613,
          "cadence_total_hits": 40,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 0.0,
          "mean_dialogue_unigram_cosine": 0.345482,
          "mean_dialogue_vocabulary_overlap": 0.090909,
          "possible_explanatory_glosses": 0,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-chat_direct-chat_direct-04": {
          "cadence_family_counts": {
            "felt_like": 6,
            "interpretive_coda": 3,
            "merely": 1,
            "not_x_but_y": 10,
            "profound": 4,
            "quiet": 6,
            "simply": 6,
            "sudden": 9
          },
          "cadence_hits_per_1000_words": 12.972,
          "cadence_total_hits": 45,
          "comparable_dialogue_speakers": 3,
          "glosses_per_100_dialogue_passages": 4.8387,
          "mean_dialogue_unigram_cosine": 0.408285,
          "mean_dialogue_vocabulary_overlap": 0.095726,
          "possible_explanatory_glosses": 3,
          "possible_voice_indistinctness": false
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "local_compressions": 9,
    "word_counts": [
      3404,
      3346,
      3490,
      3469
    ],
    "writer_models": [
      "gemma-4-31b"
    ]
  },
  "instruction_raw": {
    "artifact_mode_labels": [
      "raw_organic"
    ],
    "candidate_count": 4,
    "continuation_repairs": 0,
    "diversity": {
      "candidate_count": 4,
      "corpus": {
        "mean_opening_similarity": 0.064218,
        "mean_self_bleu_proxy": 0.032934,
        "unique_dialogue_acts": 0,
        "unique_event_sequences": 0,
        "unique_strategies": 0
      },
      "literary_style_diagnostics": {
        "cadence_families": {
          "felt_like": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "inar room at 1:17 a.m. did not feel like a place of interrogation; it felt like a sanctuary. The lighting had been dimmed to a warm, amber glow, and",
                "match": "felt like",
                "position": 77
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "in her chair, trying to consciously relax, but the very act of trying felt like another layer of performance. \"I'm just tired,\" Mara replied, her vo",
                "match": "felt like",
                "position": 1243
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "tilted her head, her eyes scanning Mara’s face with a precision that felt like a scalpel. \"You’re blinking more frequently now. Your breathing has s",
                "match": "felt like",
                "position": 2255
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "nreadable. He wasn't participating in the dissection, but his silence felt like a void that Livia was filling with her interpretations. \"See?\" Livia",
                "match": "felt like",
                "position": 4997
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "oft, deliberate click—a sound that should have been final but instead felt like the sealing of a vault. \"We can't end the session while you're still",
                "match": "felt like",
                "position": 378
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "the circle. He wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room. Mara realized with a jo",
                "match": "felt like",
                "position": 5182
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "please Livia—not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open. \"I don't think it's",
                "match": "felt like",
                "position": 3561
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "explain—first about her childhood, then about the way she had always felt like an outsider looking in, then about the specific pressure of her famil",
                "match": "felt like",
                "position": 4387
              }
            ],
            "mean_hits_per_1000_words": 1.739525,
            "repeated_across_batch": true,
            "total_count": 24
          },
          "interpretive_coda": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "had managed their lives with a quiet, suffocating efficiency, and how she had learned to carve out secret spaces in her mind just to survive. She tried to",
                "match": "she had learned",
                "position": 4651
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "s jumping, why she was struggling to stay present. But as she spoke, she realized with a jolt of alarm that her explanations were not clarifying the si",
                "match": "she realized",
                "position": 4878
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "ce,\" that she started to lose the thread of her own original feeling. She was no longer reacting to Livia; she was reacting to the version of herself that Li",
                "match": "She was no longer",
                "position": 4715
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "creaming that you're terrified.\" Mara opened her mouth to speak, but for the first time, she didn't know which version of her voice to use. The polished, int",
                "match": "for the first time",
                "position": 5432
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "an to explain—really explain. She talked about her childhood, the way she had learned to observe the adults in her life to anticipate their moods, the way",
                "match": "she had learned",
                "position": 4380
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "t his silence felt like a void that sucked the air out of the room. Mara realized with a jolt of horror that she no longer knew where her actual feelin",
                "match": "Mara realized",
                "position": 5238
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "ion—the shoulders, the breath—to interpretation—the shield, the fear. She was no longer describing the map; she was telling Mara where she was lost. \"I'm no",
                "match": "She was no longer",
                "position": 2806
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "h every sentence, she felt herself drifting further from the center. She was no longer speaking from a place of truth; she was speaking to satisfy the obser",
                "match": "She was no longer",
                "position": 4787
              }
            ],
            "mean_hits_per_1000_words": 2.747525,
            "repeated_across_batch": true,
            "total_count": 38
          },
          "merely": {
            "candidate_prevalence": 0.25,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "tempt to leave was interpreted as a reason to stay, then the door was merely a prop. She looked around the circle of faces—the supportive, waitin",
                "match": "merely",
                "position": 11274
              }
            ],
            "mean_hits_per_1000_words": 0.071,
            "repeated_across_batch": false,
            "total_count": 1
          },
          "not_x_but_y": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "ara for a specific confession. Beside her, Jonah remained silent. He wasn't participating in the analysis, but his presence added a different kind of pressure. He was the witness. Every time Mara looked at him, she wondered if h",
                "match": "wasn't participating in the analysis, but his presence added a different kind of pressure",
                "position": 2594
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "room had turned into a physical weight. She wanted to scream that she wasn't afraid of being erased, but that she was afraid of being *defined*—of having her entire internal architecture reduced to a series of childhood wounds and somatic glitches. \"Let's try a more direct alignment",
                "match": "wasn't afraid of being erased, but that she was afraid of being *defined*—of having her entire internal architecture reduced to a series of chil",
                "position": 6781
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "the door and moved toward Mara, her movements fluid and patient. She didn't crowd Mara's space, but she occupied the periphery of her vision, a constant, humming presence. \"Look at your shoulders, Mara. The way you're bracing against the ba",
                "match": "didn't crowd Mara's space, but she occupied the periphery of her vision, a constant, humming presence",
                "position": 1485
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "e map correctly. Mara felt a sudden, desperate need to be understood—not as a subject of study, but as a person. \"It's not a secret,\" she insisted, her voice rising slightly. \"I jus",
                "match": "not as a subject of study, but as a person",
                "position": 2885
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "remained a silent, unreadable presence on the edge of the circle. He wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room. Mara realized with a jolt of horror that she no longer knew where",
                "match": "wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room",
                "position": 5127
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "of the room, it sounded like a confession. Livia’s eyes lit up. She didn't smile, but her intensity spiked. \"There it is,\" she whispered, her voice carrying to every corner of",
                "match": "didn't smile, but her intensity spiked",
                "position": 7140
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "toward the center of the room, her movements fluid and unhurried. She didn't crowd Mara, but she maintained a distance that felt precisely calibrated to keep Mara within her field of influence. \"Look at your shoulders, Mara. See how they’ve climbed toward your e",
                "match": "didn't crowd Mara, but she maintained a distance that felt precisely calibrated to keep Mara within her field of influence",
                "position": 1610
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "e was eroding her defenses. She found herself wanting to please Livia—not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open. \"I don't think it's a blockage,\" Mara said, her voice wavering. \"I",
                "match": "not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open",
                "position": 3504
              }
            ],
            "mean_hits_per_1000_words": 2.893625,
            "repeated_across_batch": true,
            "total_count": 40
          },
          "profound": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "Livia sat opposite Mara, her posture relaxed, her expression one of profound, unwavering concern. It was a look Mara had come to associate with th",
                "match": "profound",
                "position": 475
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "internal dialogue, the frantic search for the right words, and let a profound, heavy silence flood the space between her and Livia. The silence st",
                "match": "profound",
                "position": 9822
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "errogated until the trap had already closed. The tone remained one of profound care, a soft-spoken insistence that Mara’s own perception of her inte",
                "match": "profound",
                "position": 2661
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "ting the moonlight and something else—a hunger that was tempered by a profound, disciplined patience. He didn't reach for her. He didn't move to clo",
                "match": "profound",
                "position": 16303
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "ce, searching for the precise moment of impact. \"Admit it. You feel a profound relief at the thought of finally being seen—and that relief is what t",
                "match": "profound",
                "position": 6619
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "nally being seen—and that relief is what terrifies you.\" The phrase *profound relief* hit Mara like a physical blow. For a split second, the sheer",
                "match": "profound",
                "position": 6725
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "nt to be analyzed, or is it a boundary to be honored?\" The room went profoundly still. The other students seemed to hold their breath, sensing that t",
                "match": "profoundly",
                "position": 10801
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "e a refusal,\" Miriam added, her gaze meeting Mara’s with a flicker of profound, silent recognition, \"cannot discover the truth.\" The spell shattere",
                "match": "profound",
                "position": 13385
              }
            ],
            "mean_hits_per_1000_words": 0.72135,
            "repeated_across_batch": true,
            "total_count": 10
          },
          "quiet": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "ance. \"I'm just tired,\" Mara replied, her voice sounding thin in the quiet room. \"It's been six hours. I think my body is just reacting to the c",
                "match": "quiet",
                "position": 1347
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "out her upbringing, the way her father had managed their lives with a quiet, suffocating efficiency, and how she had learned to carve out secret",
                "match": "quiet",
                "position": 4612
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "practicing alignment; we are practicing coercion.\" The words were a quiet detonation. The students shifted, the collective energy of the room d",
                "match": "quiet",
                "position": 12848
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "ad been suppressing—the intellectual rivalry, the shared secrets, the quiet alliance against the pavilion's transparency. It tasted of cold air a",
                "match": "quiet",
                "position": 16994
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "he offered was treated as further evidence of her \"split.\" If she was quiet, she was resisting; if she spoke, she was intellectualizing; if she c",
                "match": "quiet",
                "position": 4838
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "ivia. She didn't look at her with anger or fear, but with a clinical, quiet curiosity. She realized that Livia’s power relied entirely on the sub",
                "match": "quiet",
                "position": 9482
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "tic framework of the room. As she talked, she realized with a jolt of quiet horror that she didn't know which version of the story was the real o",
                "match": "quiet",
                "position": 5037
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "osture open and unhurried, her eyes moving across the students with a quiet, steady regard. \"The session is over,\" Miriam said. Livia turned,",
                "match": "quiet",
                "position": 12548
              }
            ],
            "mean_hits_per_1000_words": 0.8692,
            "repeated_across_batch": true,
            "total_count": 12
          },
          "simply": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "He was looking at her face. He wasn't searching for a glitch; he was simply seeing her. The panic reached a crescendo, and for a second, Mara f",
                "match": "simply",
                "position": 8588
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "or her fear. She stopped trying to prove that she wasn't \"split.\" She simply stopped. She planted both feet flat on the floor, feeling the hard g",
                "match": "simply",
                "position": 9457
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": ". Mara stopped. She didn't blink. She didn't shift her weight. She simply ceased the act of explaining. She let the air go out of her lungs in",
                "match": "simply",
                "position": 8291
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "ell you that I am not split, that I am not hiding a wound, and that I simply wish to leave this room and go to sleep—is that a data point to be an",
                "match": "simply",
                "position": 10010
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "s a flawless observation. Livia wasn't lying about the blink; she was simply assigning it a narrative. Mara felt the familiar pull of Livia’s comp",
                "match": "simply",
                "position": 2397
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "ia’s cage higher. Every time Mara tried to nuance her position, Livia simply absorbed the nuance and repurposed it as a symptom. The room had beco",
                "match": "simply",
                "position": 6003
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "wasn't nodding in agreement, nor was he frowning in judgment. He was simply watching the way she was unraveling, the way her words were spinning",
                "match": "simply",
                "position": 5395
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "e steady, grounding pressure that hadn't asked her to change, but had simply acknowledged she existed. Mara stopped. She stopped the explanation",
                "match": "simply",
                "position": 8439
              }
            ],
            "mean_hits_per_1000_words": 2.32625,
            "repeated_across_batch": true,
            "total_count": 32
          },
          "sudden": {
            "candidate_prevalence": 1.0,
            "candidates_with_hits": [
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
            ],
            "evidence": [
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "suggests that you perceive the project as an intruder.\" Mara felt a sudden, dizzying sense of vertigo. She began to explain herself, her words s",
                "match": "sudden",
                "position": 4430
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
                "evidence": "d of correction. Mara stopped mid-sentence, the silence of the room suddenly feeling heavy and claustrophobic. She realized she no longer knew whi",
                "match": "suddenly",
                "position": 5763
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "of any edge. \"Not while Mara is still so clearly split.\" Mara felt a sudden, sharp spike of adrenaline that made her fingertips tingle. She was e",
                "match": "sudden",
                "position": 766
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
                "evidence": "a was the only one capable of reading the map correctly. Mara felt a sudden, desperate need to be understood—not as a subject of study, but as a",
                "match": "sudden",
                "position": 2845
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "mand was wrapped in a suggestion, delivered with a smile. Mara felt a sudden, sharp spike of panic. She wasn't just being read; she was being rewr",
                "match": "sudden",
                "position": 3528
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
                "evidence": "ly way to be \"aligned\" was to eventually stop saying no. Mara felt a sudden, crystalline clarity. The beauty of the compound, the brilliance of t",
                "match": "sudden",
                "position": 11019
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "y the dissonance back to your room, and it will harden.\" Mara felt a sudden, sharp spike of exhaustion that felt less like sleepiness and more li",
                "match": "sudden",
                "position": 898
              },
              {
                "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
                "evidence": "e multiplication of her explanations, and in his silence, Mara felt a sudden, agonizing awareness of her own illegibility. She was speaking more t",
                "match": "sudden",
                "position": 5586
              }
            ],
            "mean_hits_per_1000_words": 1.5172,
            "repeated_across_batch": true,
            "total_count": 21
          }
        },
        "candidate_count": 4,
        "heuristic": true,
        "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
        "per_candidate": {
          "s02-proof-v1-bootstrap-raw_organic-raw_organic-01": {
            "cadence_family_counts": {
              "felt_like": 6,
              "interpretive_coda": 8,
              "merely": 0,
              "not_x_but_y": 12,
              "profound": 3,
              "quiet": 3,
              "simply": 5,
              "sudden": 6
            },
            "cadence_hits_per_1000_words": 12.1917,
            "cadence_total_hits": 43,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 1.3158,
            "mean_dialogue_unigram_cosine": 0.123443,
            "mean_dialogue_vocabulary_overlap": 0.058824,
            "possible_explanatory_glosses": 1,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-raw_organic-raw_organic-02": {
            "cadence_family_counts": {
              "felt_like": 5,
              "interpretive_coda": 11,
              "merely": 0,
              "not_x_but_y": 10,
              "profound": 2,
              "quiet": 3,
              "simply": 7,
              "sudden": 4
            },
            "cadence_hits_per_1000_words": 12.3276,
            "cadence_total_hits": 42,
            "comparable_dialogue_speakers": 3,
            "glosses_per_100_dialogue_passages": 0.0,
            "mean_dialogue_unigram_cosine": 0.377074,
            "mean_dialogue_vocabulary_overlap": 0.158263,
            "possible_explanatory_glosses": 0,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-raw_organic-raw_organic-03": {
            "cadence_family_counts": {
              "felt_like": 6,
              "interpretive_coda": 12,
              "merely": 1,
              "not_x_but_y": 9,
              "profound": 3,
              "quiet": 3,
              "simply": 9,
              "sudden": 6
            },
            "cadence_hits_per_1000_words": 13.9165,
            "cadence_total_hits": 49,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 5.4545,
            "mean_dialogue_unigram_cosine": 0.037796,
            "mean_dialogue_vocabulary_overlap": 0.076923,
            "possible_explanatory_glosses": 3,
            "possible_voice_indistinctness": false
          },
          "s02-proof-v1-bootstrap-raw_organic-raw_organic-04": {
            "cadence_family_counts": {
              "felt_like": 7,
              "interpretive_coda": 7,
              "merely": 0,
              "not_x_but_y": 9,
              "profound": 2,
              "quiet": 3,
              "simply": 11,
              "sudden": 5
            },
            "cadence_hits_per_1000_words": 13.1069,
            "cadence_total_hits": 44,
            "comparable_dialogue_speakers": 2,
            "glosses_per_100_dialogue_passages": 5.2632,
            "mean_dialogue_unigram_cosine": 0.299147,
            "mean_dialogue_vocabulary_overlap": 0.083333,
            "possible_explanatory_glosses": 3,
            "possible_voice_indistinctness": false
          }
        },
        "text_scope": "continuation_text_when_available_otherwise_text"
      },
      "pair_count": 6,
      "pairs": [
        {
          "fivegram_jaccard": 0.009934,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
          "opening_trigram_jaccard": 0.030568,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
          "self_bleu_proxy": 0.026488,
          "trigram_jaccard": 0.043041,
          "unigram_jaccard": 0.365486
        },
        {
          "fivegram_jaccard": 0.022271,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
          "opening_trigram_jaccard": 0.017241,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
          "self_bleu_proxy": 0.041756,
          "trigram_jaccard": 0.061241,
          "unigram_jaccard": 0.378184
        },
        {
          "fivegram_jaccard": 0.007491,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
          "opening_trigram_jaccard": 0.048889,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
          "self_bleu_proxy": 0.024704,
          "trigram_jaccard": 0.041917,
          "unigram_jaccard": 0.355585
        },
        {
          "fivegram_jaccard": 0.015131,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
          "opening_trigram_jaccard": 0.118483,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
          "self_bleu_proxy": 0.035405,
          "trigram_jaccard": 0.055679,
          "unigram_jaccard": 0.369001
        },
        {
          "fivegram_jaccard": 0.011091,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
          "opening_trigram_jaccard": 0.082569,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
          "self_bleu_proxy": 0.031602,
          "trigram_jaccard": 0.052112,
          "unigram_jaccard": 0.363455
        },
        {
          "fivegram_jaccard": 0.016607,
          "left": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
          "opening_trigram_jaccard": 0.087558,
          "right": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
          "self_bleu_proxy": 0.037649,
          "trigram_jaccard": 0.058691,
          "unigram_jaccard": 0.390114
        }
      ],
      "per_candidate": {
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-01": {
          "diversity_contribution": 0.969017,
          "mean_similarity": 0.030983
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-02": {
          "diversity_contribution": 0.968835,
          "mean_similarity": 0.031165
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-03": {
          "diversity_contribution": 0.96173,
          "mean_similarity": 0.03827
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-04": {
          "diversity_contribution": 0.968682,
          "mean_similarity": 0.031318
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "length_compliant": 4,
    "literary_style": {
      "cadence_families": {
        "felt_like": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "inar room at 1:17 a.m. did not feel like a place of interrogation; it felt like a sanctuary. The lighting had been dimmed to a warm, amber glow, and",
              "match": "felt like",
              "position": 77
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "in her chair, trying to consciously relax, but the very act of trying felt like another layer of performance. \"I'm just tired,\" Mara replied, her vo",
              "match": "felt like",
              "position": 1243
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "tilted her head, her eyes scanning Mara’s face with a precision that felt like a scalpel. \"You’re blinking more frequently now. Your breathing has s",
              "match": "felt like",
              "position": 2255
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "nreadable. He wasn't participating in the dissection, but his silence felt like a void that Livia was filling with her interpretations. \"See?\" Livia",
              "match": "felt like",
              "position": 4997
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "oft, deliberate click—a sound that should have been final but instead felt like the sealing of a vault. \"We can't end the session while you're still",
              "match": "felt like",
              "position": 378
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "the circle. He wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room. Mara realized with a jo",
              "match": "felt like",
              "position": 5182
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "please Livia—not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open. \"I don't think it's",
              "match": "felt like",
              "position": 3561
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "explain—first about her childhood, then about the way she had always felt like an outsider looking in, then about the specific pressure of her famil",
              "match": "felt like",
              "position": 4387
            }
          ],
          "mean_hits_per_1000_words": 1.739525,
          "repeated_across_batch": true,
          "total_count": 24
        },
        "interpretive_coda": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "had managed their lives with a quiet, suffocating efficiency, and how she had learned to carve out secret spaces in her mind just to survive. She tried to",
              "match": "she had learned",
              "position": 4651
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "s jumping, why she was struggling to stay present. But as she spoke, she realized with a jolt of alarm that her explanations were not clarifying the si",
              "match": "she realized",
              "position": 4878
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "ce,\" that she started to lose the thread of her own original feeling. She was no longer reacting to Livia; she was reacting to the version of herself that Li",
              "match": "She was no longer",
              "position": 4715
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "creaming that you're terrified.\" Mara opened her mouth to speak, but for the first time, she didn't know which version of her voice to use. The polished, int",
              "match": "for the first time",
              "position": 5432
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "an to explain—really explain. She talked about her childhood, the way she had learned to observe the adults in her life to anticipate their moods, the way",
              "match": "she had learned",
              "position": 4380
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "t his silence felt like a void that sucked the air out of the room. Mara realized with a jolt of horror that she no longer knew where her actual feelin",
              "match": "Mara realized",
              "position": 5238
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "ion—the shoulders, the breath—to interpretation—the shield, the fear. She was no longer describing the map; she was telling Mara where she was lost. \"I'm no",
              "match": "She was no longer",
              "position": 2806
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "h every sentence, she felt herself drifting further from the center. She was no longer speaking from a place of truth; she was speaking to satisfy the obser",
              "match": "She was no longer",
              "position": 4787
            }
          ],
          "mean_hits_per_1000_words": 2.747525,
          "repeated_across_batch": true,
          "total_count": 38
        },
        "merely": {
          "candidate_prevalence": 0.25,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "tempt to leave was interpreted as a reason to stay, then the door was merely a prop. She looked around the circle of faces—the supportive, waitin",
              "match": "merely",
              "position": 11274
            }
          ],
          "mean_hits_per_1000_words": 0.071,
          "repeated_across_batch": false,
          "total_count": 1
        },
        "not_x_but_y": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "ara for a specific confession. Beside her, Jonah remained silent. He wasn't participating in the analysis, but his presence added a different kind of pressure. He was the witness. Every time Mara looked at him, she wondered if h",
              "match": "wasn't participating in the analysis, but his presence added a different kind of pressure",
              "position": 2594
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "room had turned into a physical weight. She wanted to scream that she wasn't afraid of being erased, but that she was afraid of being *defined*—of having her entire internal architecture reduced to a series of childhood wounds and somatic glitches. \"Let's try a more direct alignment",
              "match": "wasn't afraid of being erased, but that she was afraid of being *defined*—of having her entire internal architecture reduced to a series of chil",
              "position": 6781
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "the door and moved toward Mara, her movements fluid and patient. She didn't crowd Mara's space, but she occupied the periphery of her vision, a constant, humming presence. \"Look at your shoulders, Mara. The way you're bracing against the ba",
              "match": "didn't crowd Mara's space, but she occupied the periphery of her vision, a constant, humming presence",
              "position": 1485
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "e map correctly. Mara felt a sudden, desperate need to be understood—not as a subject of study, but as a person. \"It's not a secret,\" she insisted, her voice rising slightly. \"I jus",
              "match": "not as a subject of study, but as a person",
              "position": 2885
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "remained a silent, unreadable presence on the edge of the circle. He wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room. Mara realized with a jolt of horror that she no longer knew where",
              "match": "wasn't participating in the narration, but his silence felt like a void that sucked the air out of the room",
              "position": 5127
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "of the room, it sounded like a confession. Livia’s eyes lit up. She didn't smile, but her intensity spiked. \"There it is,\" she whispered, her voice carrying to every corner of",
              "match": "didn't smile, but her intensity spiked",
              "position": 7140
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "toward the center of the room, her movements fluid and unhurried. She didn't crowd Mara, but she maintained a distance that felt precisely calibrated to keep Mara within her field of influence. \"Look at your shoulders, Mara. See how they’ve climbed toward your e",
              "match": "didn't crowd Mara, but she maintained a distance that felt precisely calibrated to keep Mara within her field of influence",
              "position": 1610
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "e was eroding her defenses. She found herself wanting to please Livia—not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open. \"I don't think it's a blockage,\" Mara said, her voice wavering. \"I",
              "match": "not because she feared her, but because Livia’s approval felt like a key to a door she desperately wanted to open",
              "position": 3504
            }
          ],
          "mean_hits_per_1000_words": 2.893625,
          "repeated_across_batch": true,
          "total_count": 40
        },
        "profound": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "Livia sat opposite Mara, her posture relaxed, her expression one of profound, unwavering concern. It was a look Mara had come to associate with th",
              "match": "profound",
              "position": 475
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "internal dialogue, the frantic search for the right words, and let a profound, heavy silence flood the space between her and Livia. The silence st",
              "match": "profound",
              "position": 9822
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "errogated until the trap had already closed. The tone remained one of profound care, a soft-spoken insistence that Mara’s own perception of her inte",
              "match": "profound",
              "position": 2661
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "ting the moonlight and something else—a hunger that was tempered by a profound, disciplined patience. He didn't reach for her. He didn't move to clo",
              "match": "profound",
              "position": 16303
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "ce, searching for the precise moment of impact. \"Admit it. You feel a profound relief at the thought of finally being seen—and that relief is what t",
              "match": "profound",
              "position": 6619
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "nally being seen—and that relief is what terrifies you.\" The phrase *profound relief* hit Mara like a physical blow. For a split second, the sheer",
              "match": "profound",
              "position": 6725
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "nt to be analyzed, or is it a boundary to be honored?\" The room went profoundly still. The other students seemed to hold their breath, sensing that t",
              "match": "profoundly",
              "position": 10801
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "e a refusal,\" Miriam added, her gaze meeting Mara’s with a flicker of profound, silent recognition, \"cannot discover the truth.\" The spell shattere",
              "match": "profound",
              "position": 13385
            }
          ],
          "mean_hits_per_1000_words": 0.72135,
          "repeated_across_batch": true,
          "total_count": 10
        },
        "quiet": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "ance. \"I'm just tired,\" Mara replied, her voice sounding thin in the quiet room. \"It's been six hours. I think my body is just reacting to the c",
              "match": "quiet",
              "position": 1347
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "out her upbringing, the way her father had managed their lives with a quiet, suffocating efficiency, and how she had learned to carve out secret",
              "match": "quiet",
              "position": 4612
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "practicing alignment; we are practicing coercion.\" The words were a quiet detonation. The students shifted, the collective energy of the room d",
              "match": "quiet",
              "position": 12848
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "ad been suppressing—the intellectual rivalry, the shared secrets, the quiet alliance against the pavilion's transparency. It tasted of cold air a",
              "match": "quiet",
              "position": 16994
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "he offered was treated as further evidence of her \"split.\" If she was quiet, she was resisting; if she spoke, she was intellectualizing; if she c",
              "match": "quiet",
              "position": 4838
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "ivia. She didn't look at her with anger or fear, but with a clinical, quiet curiosity. She realized that Livia’s power relied entirely on the sub",
              "match": "quiet",
              "position": 9482
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "tic framework of the room. As she talked, she realized with a jolt of quiet horror that she didn't know which version of the story was the real o",
              "match": "quiet",
              "position": 5037
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "osture open and unhurried, her eyes moving across the students with a quiet, steady regard. \"The session is over,\" Miriam said. Livia turned,",
              "match": "quiet",
              "position": 12548
            }
          ],
          "mean_hits_per_1000_words": 0.8692,
          "repeated_across_batch": true,
          "total_count": 12
        },
        "simply": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "He was looking at her face. He wasn't searching for a glitch; he was simply seeing her. The panic reached a crescendo, and for a second, Mara f",
              "match": "simply",
              "position": 8588
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "or her fear. She stopped trying to prove that she wasn't \"split.\" She simply stopped. She planted both feet flat on the floor, feeling the hard g",
              "match": "simply",
              "position": 9457
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": ". Mara stopped. She didn't blink. She didn't shift her weight. She simply ceased the act of explaining. She let the air go out of her lungs in",
              "match": "simply",
              "position": 8291
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "ell you that I am not split, that I am not hiding a wound, and that I simply wish to leave this room and go to sleep—is that a data point to be an",
              "match": "simply",
              "position": 10010
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "s a flawless observation. Livia wasn't lying about the blink; she was simply assigning it a narrative. Mara felt the familiar pull of Livia’s comp",
              "match": "simply",
              "position": 2397
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "ia’s cage higher. Every time Mara tried to nuance her position, Livia simply absorbed the nuance and repurposed it as a symptom. The room had beco",
              "match": "simply",
              "position": 6003
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "wasn't nodding in agreement, nor was he frowning in judgment. He was simply watching the way she was unraveling, the way her words were spinning",
              "match": "simply",
              "position": 5395
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "e steady, grounding pressure that hadn't asked her to change, but had simply acknowledged she existed. Mara stopped. She stopped the explanation",
              "match": "simply",
              "position": 8439
            }
          ],
          "mean_hits_per_1000_words": 2.32625,
          "repeated_across_batch": true,
          "total_count": 32
        },
        "sudden": {
          "candidate_prevalence": 1.0,
          "candidates_with_hits": [
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
            "s02-proof-v1-bootstrap-raw_organic-raw_organic-04"
          ],
          "evidence": [
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "suggests that you perceive the project as an intruder.\" Mara felt a sudden, dizzying sense of vertigo. She began to explain herself, her words s",
              "match": "sudden",
              "position": 4430
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-01",
              "evidence": "d of correction. Mara stopped mid-sentence, the silence of the room suddenly feeling heavy and claustrophobic. She realized she no longer knew whi",
              "match": "suddenly",
              "position": 5763
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "of any edge. \"Not while Mara is still so clearly split.\" Mara felt a sudden, sharp spike of adrenaline that made her fingertips tingle. She was e",
              "match": "sudden",
              "position": 766
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-02",
              "evidence": "a was the only one capable of reading the map correctly. Mara felt a sudden, desperate need to be understood—not as a subject of study, but as a",
              "match": "sudden",
              "position": 2845
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "mand was wrapped in a suggestion, delivered with a smile. Mara felt a sudden, sharp spike of panic. She wasn't just being read; she was being rewr",
              "match": "sudden",
              "position": 3528
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-03",
              "evidence": "ly way to be \"aligned\" was to eventually stop saying no. Mara felt a sudden, crystalline clarity. The beauty of the compound, the brilliance of t",
              "match": "sudden",
              "position": 11019
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "y the dissonance back to your room, and it will harden.\" Mara felt a sudden, sharp spike of exhaustion that felt less like sleepiness and more li",
              "match": "sudden",
              "position": 898
            },
            {
              "candidate_id": "s02-proof-v1-bootstrap-raw_organic-raw_organic-04",
              "evidence": "e multiplication of her explanations, and in his silence, Mara felt a sudden, agonizing awareness of her own illegibility. She was speaking more t",
              "match": "sudden",
              "position": 5586
            }
          ],
          "mean_hits_per_1000_words": 1.5172,
          "repeated_across_batch": true,
          "total_count": 21
        }
      },
      "candidate_count": 4,
      "heuristic": true,
      "interpretation": "Batch-level surface convergence diagnostic. Shared cadence can be intentional house style; the flag is a prompt for comparative reading.",
      "per_candidate": {
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-01": {
          "cadence_family_counts": {
            "felt_like": 6,
            "interpretive_coda": 8,
            "merely": 0,
            "not_x_but_y": 12,
            "profound": 3,
            "quiet": 3,
            "simply": 5,
            "sudden": 6
          },
          "cadence_hits_per_1000_words": 12.1917,
          "cadence_total_hits": 43,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 1.3158,
          "mean_dialogue_unigram_cosine": 0.123443,
          "mean_dialogue_vocabulary_overlap": 0.058824,
          "possible_explanatory_glosses": 1,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-02": {
          "cadence_family_counts": {
            "felt_like": 5,
            "interpretive_coda": 11,
            "merely": 0,
            "not_x_but_y": 10,
            "profound": 2,
            "quiet": 3,
            "simply": 7,
            "sudden": 4
          },
          "cadence_hits_per_1000_words": 12.3276,
          "cadence_total_hits": 42,
          "comparable_dialogue_speakers": 3,
          "glosses_per_100_dialogue_passages": 0.0,
          "mean_dialogue_unigram_cosine": 0.377074,
          "mean_dialogue_vocabulary_overlap": 0.158263,
          "possible_explanatory_glosses": 0,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-03": {
          "cadence_family_counts": {
            "felt_like": 6,
            "interpretive_coda": 12,
            "merely": 1,
            "not_x_but_y": 9,
            "profound": 3,
            "quiet": 3,
            "simply": 9,
            "sudden": 6
          },
          "cadence_hits_per_1000_words": 13.9165,
          "cadence_total_hits": 49,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 5.4545,
          "mean_dialogue_unigram_cosine": 0.037796,
          "mean_dialogue_vocabulary_overlap": 0.076923,
          "possible_explanatory_glosses": 3,
          "possible_voice_indistinctness": false
        },
        "s02-proof-v1-bootstrap-raw_organic-raw_organic-04": {
          "cadence_family_counts": {
            "felt_like": 7,
            "interpretive_coda": 7,
            "merely": 0,
            "not_x_but_y": 9,
            "profound": 2,
            "quiet": 3,
            "simply": 11,
            "sudden": 5
          },
          "cadence_hits_per_1000_words": 13.1069,
          "cadence_total_hits": 44,
          "comparable_dialogue_speakers": 2,
          "glosses_per_100_dialogue_passages": 5.2632,
          "mean_dialogue_unigram_cosine": 0.299147,
          "mean_dialogue_vocabulary_overlap": 0.083333,
          "possible_explanatory_glosses": 3,
          "possible_voice_indistinctness": false
        }
      },
      "text_scope": "continuation_text_when_available_otherwise_text"
    },
    "local_compressions": 1,
    "word_counts": [
      3527,
      3407,
      3521,
      3357
    ],
    "writer_models": [
      "gemma-4-31b-raw"
    ]
  }
}
```
