from .domain import RetrievalResult, Strategy, ParaFolder, Chunk
from .store import ChromaStore
from .classifier import Classifier


SCHEMA_VERSION = "V1"

class Retrieve():

	def __init__(self, store : ChromaStore, classifier : Classifier):
		self.store 		=	store
		self.classifier =	classifier


	def _build_result(self, search_result : list[Chunk], query_category : ParaFolder, fell_back_to_flat : bool, strategy : Strategy, k : int) -> RetrievalResult:

		result : RetrievalResult = RetrievalResult(
			chunks 				= search_result, 
			query_category 		= query_category,
			fell_back_to_flat 	= fell_back_to_flat,
			strategy 			= strategy,
			k 					= k,
			version 			= SCHEMA_VERSION
		) 

		return result


	def _retrieve_flat(self, query : str, k : int) -> list[Chunk]:

		return self.store.search_flat(query, k)


	def _retrieve_para(self, query: str, para_category : ParaFolder, k : int) -> list[Chunk]:

		return self.store.search_filtered(query, para_category, k) 


	def retrieve(self, query : str, strategy : Strategy, k : int) -> RetrievalResult:

		query_category : ParaFolder | None = None

		search_result : list[Chunk]

		fell_back_to_flat : bool = False

		if strategy == Strategy.FLAT:

			search_result 	= self._retrieve_flat(query, k)

		elif strategy == Strategy.PARA:

			query_category 	= self.classifier.classify_query(query)
			search_result 	= self._retrieve_para(query, query_category, k)

			if not search_result:

				fell_back_to_flat = True

				search_result = self._retrieve_flat(query, k)

		retrieved : RetrievalResult = self._build_result(search_result, query_category, fell_back_to_flat, strategy, k)

		return retrieved


