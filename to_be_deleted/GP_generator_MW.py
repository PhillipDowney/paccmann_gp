"""GP Classes module."""

import torch
from rdkit import Chem
from rdkit.Chem.Descriptors import MolWt, qed
from skopt import gp_minimize
from skopt.space import Real
from paccmann_generator.drug_evaluators.sas  import  SAS

class GP_generator_for_MW():
    """ SVAE GP generator minimisation functions """

    def __init__(self, SVAEmodel):
        """
        Initialization.

        Args:
            SVAEmodel: the loaded pretrained SVAE model with its parameters and smiles_language.
        """
        super(GP_generator_for_MW, self).__init__()
        self.SVAEmodel=SVAEmodel
        self.sas = SAS()

    def generate_smiles(self,latent_point,tosmiles=True):
        """
        Generate a smiles or selfies code from latent latent_point.

        Args:
            latent_point: the input latent point with shape '[1,1,latent_dim]'
            tomsiles: boolean to specify if output should be smiles (True) or   numerical sequence (False)
        """

        mols_numerical=self.SVAEmodel.generate(latent_point,     prime_input=torch.LongTensor([self.SVAEmodel.smiles_language.start_index]), end_token=torch.LongTensor([self.SVAEmodel.smiles_language.stop_index]))

        # if smiles are required instead of selfies
        if tosmiles==True:
            smiles_num_tuple = [(
            self.SVAEmodel.smiles_language.token_indexes_to_smiles(num_mol.tolist()),
                torch.cat([num_mol.long(),
                torch.tensor(2 * [self.SVAEmodel.smiles_language.stop_index])]
                )) for num_mol in iter(mols_numerical)]

            numericals = [sm[1] for sm in smiles_num_tuple]

            smiles = [self.SVAEmodel.smiles_language.selfies_to_smiles(sm[0])
                    for sm in smiles_num_tuple]
            imgs = [Chem.MolFromSmiles(s, sanitize=True) for s in smiles]

            valid_idxs = [ind for ind in range(len(imgs)) if imgs[ind] is not None]

            smiles = [smiles[ind] for ind in range(len(imgs))
                    if not ( imgs[ind] is None)]

            return self.generate_smiles(latent_point) if smiles==[] else smiles
        else:
            return mols_numerical


    def Optimisation_process(self, minimisation,target=None):
        """
        Optimisation with GP

        Args:
            targetMW: target molecular weight of type float or int
        """
        Boundaries_latentdim=[(-5.0, 5.0)]*256
        #Target=Real(name='targetMW',300)
        if minimisation=='MW':
            function=self.MW_minimisation_function
            self.target=target
        elif minimisation=='QED':
            function=self.QED_minimisation_function
        elif minimisation =="SA":
            function=self.SAs_minimisation_function

        res = gp_minimize(function,
                      dimensions=Boundaries_latentdim, #256 is latent dimensions
                      acq_func="EI",
                      n_calls=150,
                      n_initial_points=20,
                      initial_point_generator='random',
                      random_state=1234)

        return res

    def MW_minimisation_function(self, latentlist):
        """
        Function to minimise in Bayesian optimisation for MW

        Args:
            latentarray: the input list of latent coordinates of len=latent_dim
            targetMW: target molecular weight of type float or int
        """

        smiles=[]
        latent_point=torch.tensor([[latentlist]])
        while smiles ==[]: #loop as some molecules are not valid smiles
            smiles=self.generate_smiles(latent_point)
        mweights=[MolWt(Chem.MolFromSmiles(smile)) for smile in smiles]

        return abs(self.target-mweights[0])

    def QED_minimisation_function(self, latentlist):
        """
        Function to minimise in Bayesian optimisation for QED

        Args:
            latentarray: the input list of latent coordinates of len=latent_dim
        """

        smiles=[]
        latent_point=torch.tensor([[latentlist]])
        while smiles ==[]: #loop as some molecules are not valid smiles
            smiles=self.generate_smiles(latent_point)
        QEDvalue=[qed(Chem.MolFromSmiles(smile)) for smile in smiles]

        return 1-QEDvalue[0]

    def SAs_minimisation_function(self, latentlist):
        """
        Function to minimise in Bayesian optimisation for SA score

        Args:
            latentarray: the input list of latent coordinates of len=latent_dim
        """

        smiles=[]
        latent_point=torch.tensor([[latentlist]])
        while smiles ==[]: #loop as some molecules are not valid smiles
            smiles=self.generate_smiles(latent_point)
        SAscore=[self.sas(smile) for smile in smiles]

        return SAscore[0]

        #sas score between 1-10