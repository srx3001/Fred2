# This code is part of the Fred2 distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.
__author__ = 'szolek', 'walzer', 'schubert'

import logging
import re
from Base import MetadataLogger


#ENUMs for variation types like SNP, deletion, insertion, framshift deletion, frameshift insertion
VariationType = (lambda **enums: type('Enum', (), enums))(SNP=0, DEL=1, INS=2, FSDEL=3, FSINS=4, UNKNOWN=5)


# def parse_annotation(annotations, details=None):
#     """
#     parses an annotation string (http://www.hgvs.org/mutnomen/quickref.html)
#         - e.g. from ANNOVAR: (string) ANK3:NM_001204403:exon10:c.939delG:p.M313fs,ANK3:NM_020987:exon9:c.957delG:p.M319fs,ANK3:NM_001204404:exon9:c.906delG:p.M302fs,
#         - e.g. cosmic: (list of dict) ITGAV	ENST00000261023	71212	c.1502C>A	p.S501Y	...
#     :param annotations: the ANNOVAR annotation string
#     :param details: the ANNOVAR variant details
#     :return:
#     """
#     mut_syn = dict()
#     #gss - old ANNOVAR stuff
#     # HAT1:NM_003642:exon11:c.A1208T:p.Q403L,
#     # NBPF10:NM_001039703:exon4:p.A179D:GCT->GAT:+,
#
#     #gsvar - ANNOVAR uses UCSC?
#     # RANBP2:NM_006267:exon14:c.A1954G:p.I652V,
#     # ANAPC1:NM_022662:exon12:c.C1393T:p.Q465X,
#     # NCBP1:NM_002486:exon9:c.913_914insG:p.G305fs,
#     # ANK3:NM_001204403:exon10:c.939delG:p.M313fs,ANK3:NM_020987:exon9:c.957delG:p.M319fs,ANK3:NM_001204404:exon9:c.906delG:p.M302fs,
#
#     #cosmic - http://www.hgvs.org/mutnomen/ (http://www.hgvs.org/mutnomen/quickref.html)
#     # Gene Name	Accession Number    CDS Mutation Syntax	AA Mutation Syntax
#     # TP53	ENST00000269305	c.?	p.E286K
#     # MAP3K6	NM_004672	c.2483C>T	p.T828I	...
#     # ITGAV	ENST00000261023	c.1502C>A	p.S501Y	...
#     # TP53	ENST00000269305	c.847_848insT	p.R283fs*23
#
#     #maybe use HGVS 0.3.3dev-d13418a64c51 ??
#     #TODO needs indel handling
#     if isinstance(annotations, str):
#         annotations = [x for x in annotations.split(',') if x]  # removes trailing list entry ''
#         for a in annotations:
#                     t, c, p = [None]*3
#                     for i in a.split(':'):
#                         if i.startswith(('NM_', 'ENST')):
#                                 t = i
#                         elif i.startswith('c.'):
#                                 c = i
#                         elif i.startswith('p.'):
#                                 p = i
#                     if t and c and p:
#                         mut_syn[t] = MutationSyntax(details, c, p)
#                     else:
#                         logging.warn('Insufficient variation coding annotation data (entry is ' + str(a) + ')')
#
#     elif isinstance(annotations, list) \
#             and all(isinstance(x, dict)
#                     and 'Accession Number' in x and 'CDS Mutation Syntax' in x and 'AA Mutation Syntax' in x
#                     for x in annotations):
#         for a in annotations:
#             mut_syn[a['Accession Number']] = MutationSyntax(details, a['CDS Mutation Syntax'], a['AA Mutation Syntax'])
#     else:
#         logging.warn('Unusable variation annotation input')
#     return mut_syn


class MutationSyntax():
    """
    This class represents the mutation syntax of a variant and stores its transcript and protein position
    """
    def __init__(self, transID, transPos, protPos, cds, aas):
        """
        Constructor

        TODO: is protPos always given? what about synonymous variants?

        :param transID: (str) the transcript id
        :param transPos: (int) the position of the variant within the transcript
        :param protPos: (int) the protein position of the variant within the transcript
        :param cds: (str) the complete cds_mutation_syntax string
        :param aas: (str) the complete protein_mutation_syntax string
        """
        self.transID = transID
        self.tranPos = transPos
        self.protPos = protPos
        self.cdsMutationSyntax = cds  #c. ...
        self.aaMutationSyntax = aas  #p. ...


class Variant(MetadataLogger):
    def __init__(self, id, type, chrom, genomePos, ref, obs, coding, isHomozygous, isSynonymous, metadata=None):
        """
        Constructor

        :param id: (str) Variant id
        :param type: (Enum.VariationType) An Enum type of the variant either SNP, DEL, or INS
        :param chrom: (str) The chromosome on which the variant lies
        :param genomePos: (int) The genomic position of the variant
        :param ref: (str) The reference seq at the genomic position
        :param obs: (str) The observed variation at the genomic position
        :param isHomozygous: (bool) defines if variant is homozygous or not
        :param isSynonymous: (bool) defines if variant is a synonymous mutation or not
        :param metadata: ({}) meta information (not relevant for core functionality of Fred2)
        :param coding: ({str:MutationSyntax}) A dictionary of associated transcripts. Key=transcript_id, value=MutationSyntax
        """
        MetadataLogger.__init__(self)
        self.id = id
        self.type = type
        self.chrom = chrom
        self.genomePos = genomePos
        self.ref = ref
        self.obs = obs
        self.gene = None
        self.isHomozygous = isHomozygous
        self.isSynonymous = isSynonymous
        self.offsets = {}
        self.coding = coding  # dict transcript_id:MutationSyntax

        if metadata is not None:
            for meta in metadata:
                self.log_metadata(meta, metadata[meta])

    def __repr__(self):
        return "Variant(%s%i%s)"%(self.ref, self.genomePos, self.obs)

    def get_transcript_position(self, transcriptId):
        """
        returns the specific transcript position of a given transcript_id. If variant is not associated with the
        given transcript id the function throws a KeyError
        :param transcriptId: (str) A transcript_id
        :return: (int) transcript position
        :raises: KeyError
        """
        offsetID = ""
        transID = transcriptId.split(":FRED2_")
        if len(transID) > 1:
            offsetID = transID[1]
        try:
            return self.coding[transID[0]].tranPos+self.offsets.get((transID[0], offsetID), 0)
        except KeyError:
            raise KeyError("Transcript ID %s not associated with variant %s"%(str(transID[0]), self.__str__()))

    def get_protein_position(self, transcriptId):
        """
        returns the specific protein position of a given transcript_id. If variant is not associated with the
        given transcript id the function throws a KeyError
        :param transcriptId:  (str) A transcript_id
        :return: (int) the protein position of the variant
        """
        try:
            return self.coding[transcriptId].protPos
        except KeyError:
            raise KeyError("Transcript ID %s not associated with variant %s"%(str(transcriptId), self.__str__()))
