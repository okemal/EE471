# Taxonomy and species information

The application compares **41 species concepts from the IUCN Cat Classification
Task Force's 2017 treatment**: 40 wild cats and the domestic cat. This is a
deliberately versioned label set, not a claim that every currently proposed cat
species is represented. The primary reference is [Kitchener et al. (2017), *A
revised taxonomy of the Felidae*, Cat News Special Issue
11](https://repository.si.edu/handle/10088/32616).

The [IUCN/SSC Cat Specialist Group's classification
page](https://www.catsg.org/classification), checked on 2 November 2026, describes
that treatment as comprising 14 genera and two subfamilies and states that a
review is in progress. Its [living-species
index](https://www.catsg.org/cats/livingspecies) provides the corresponding wild
species accounts and lists the domestic cat separately. The app does not infer a
species count from Wikipedia or combine competing checklists at runtime.

## Data files

`backend/app/data/species.json` is an array of 41 records. Each has a stable
`id`, common and scientific names, genus, subfamily, Wikipedia article title,
short description, broad range, habitat, three features to compare, and a
`source_url`. `taxonomy_note` records relevant caveats; `aliases` assists search
and interpretation. An alias is not necessarily a name accepted by the pinned
classification. `backend/app/data/taxonomy.json` records the catalogue's scope,
version, review date and reference URLs.

The seven *Panthera* and *Neofelis* species belong to Pantherinae. The other 34
entries belong to Felinae. Domestic breeds, colour variants, hybrids and
subspecies are not separate classifier targets. In particular, “black panther”
does not identify a distinct species; both leopards and jaguars can be
melanistic. A domestic cat match is a species suggestion, not a breed diagnosis.

## Profile provenance

The wild-cat profiles are short, independently worded summaries of the linked
[IUCN/SSC Cat Specialist Group
accounts](https://www.catsg.org/cats/livingspecies), reviewed on 2 November 2026.
The domestic-cat profile uses the [Felidae Conservation Fund's domestic cat
account](https://felidaefund.org/learn/cats/domestic-cat). Each record links
directly to its supporting account. Range labels are intentionally broad and
describe a species' distribution, not an animal's location inferred from a
photograph.

These are educational summaries, not reproductions of the source articles.
Typical coat and body features are useful comparisons but are not exclusive
diagnostic keys. Lighting, age, sex, season, unusual colour forms and incomplete
views can hide or change these features. The catalogue deliberately omits
conservation categories, population totals and detailed subspecies information:
those need separate dated assessments and are liable to differ between sources.

Wikipedia titles are fixed catalogue entries for optional article retrieval.
Wikipedia may update independently or use a different species concept. Preserve
the catalogue's scientific name, scope and caveats when showing supplementary
Wikipedia information; do not silently replace the classifier's taxonomy with
article text. In particular, a modern article may cover a narrower concept than
the app's pampas-cat or northern-tiger-cat label. A failed online lookup should
leave the sourced local profile available.

## Known taxonomic limitations

**Pampas cats.** The app retains the broad *Leopardus colocola* concept used in
2017. Later work splits the group into several species. The app's label must not
be interpreted as identifying one of these narrower taxa. See the [CatSG
account](https://www.catsg.org/living-species-pampascat) and the [Pampas Cat Working
Group's research library](https://pampascatwg.com/library/). The spelling
*Leopardus colocolo* occurs in other references and is stored as an alias rather
than as an additional target.

**Tiger cats.** The app uses the 2017 *L. tigrinus* and *L. guttulus* concepts.
Research has since refined the group. A [2024
study](https://doi.org/10.1038/s41598-024-52379-8) supported the clouded tiger cat,
*L. pardinoides*. [Lescroart et al.
(2026)](https://pubmed.ncbi.nlm.nih.gov/42753727/) analysed genomes and recognised
five tiger-cat species, describing *L. tilcayo* and a new subspecies. These newer
units are not separately represented. A northern tiger-cat match therefore
refers to the older, broader concept and cannot establish which newer species
is present.

**Wildcats and domestic cats.** The pinned classification treats *Felis catus*,
*F. silvestris*, *F. lybica* and *F. bieti* as separate species. Their relationship
and boundaries have received different treatments. Domestic–wildcat
hybridisation means that coat appearance cannot establish genetic purity. The
[European wildcat](https://www.catsg.org/living-species-europeanwildcat),
[Afro-Asiatic wildcat](https://www.catsg.org/living-species-africanwildcat) and
[Chinese mountain cat](https://www.catsg.org/living-species-chinesemountaincat)
profiles explain the underlying uncertainty. The app's *F. lybica* label includes
the African and Asiatic forms considered together in 2017.

**Other names and lookalikes.** The app follows *Herpailurus yagouaroundi* for the
jaguarundi and *Caracal aurata* for the African golden cat, matching the reference.
The alternatives *Puma yagouaroundi* and *Caracal auratus* are retained as aliases.
The two clouded leopards and the two leopard cats are separate labels, but their
visual overlap can require origin information and expert examination to resolve.
The correct scientific name of the rusty-spotted cat is *Prionailurus
rubiginosus*; this catalogue does not copy the typographical error in the CatSG
index.

## Interpreting a result

A zero-shot model compares an image with the configured candidate names. The
highest score is evidence of relative similarity within that candidate set,
not proof of species identity or a calibrated probability. An out-of-scope
species, hybrid, artwork or unclear image can resemble a supported label. A
rejection means the application did not obtain a sufficiently supported match;
it does not prove that the photograph contains no cat.

Updating the catalogue is a versioned model change: review a complete taxonomic
reference, preserve old identifiers or document migrations, regenerate text
embeddings, update scope labels, and re-evaluate acceptance thresholds and
lookalike cases. Do not add a few newer split taxa beside their unsplit parent
species concept, because that creates overlapping targets.
