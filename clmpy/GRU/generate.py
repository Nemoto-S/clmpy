# -*- coding: utf-8 -*-
# 240620

import os
from argparse import ArgumentParser, FileType
import yaml

import numpy as np
import pandas as pd
import torch

from .model import GRU
from ..preprocess import prep_token
from ..get_args import get_argument


class Generator():
    def __init__(self,args,model):
        self.args = args
        self.id2sm = args.token.id2sm
        self.model = model.to(args.device)
        self.maxlen = args.maxlen
        if len(args.model_path) > 0:
            self._load(args.model_path)
        self.device = args.device

    def _load(self,path):
        self.model.load_state_dict(torch.load(path))

    def _generate_batch(self,latent):
        # latent: [B, H]
        latent = latent.to(self.device)
        token_ids = np.zeros((self.maxlen,latent.size(0)))
        token_ids[0,:] = 1
        token_ids = torch.tensor(token_ids,dtype=torch.long).to(self.device)
        for i in range(1,self.maxlen):
            token_ids_seq = token_ids[i-1,:].unsqueeze(0)
            if i == 1:
                output, latent = self.model.decoder(token_ids_seq,latent)
            else:
                output, latent = self.model.decoder.gru2out(token_ids_seq,latent)
            _, new_id = output.max(dim=2)
            is_end_token = token_ids_seq == 2
            is_pad_token = token_ids_seq == 0
            judge = torch.logical_or(is_end_token,is_pad_token)
            if judge.sum().item() == judge.numel():
                token_ids = token_ids[:i,:]
                break
            new_id[judge] = 0
            token_ids[i,:] = new_id
        pred = token_ids[1:,:]
        res = []
        for v in pred.T:
            p = [self.id2sm[j.item()] for j in v]
            p_str = "".join(p).split(self.id2sm[2])[0].replace("R","Br").replace("L","Cl")
            res.append(p_str)
        return res

    def generate(self,latent):
        # latent: [B, H]
        self.model.eval()
        if type(latent) == pd.DataFrame:
            latent = latent.values
        latent = [torch.Tensor(latent[i:i+self.args.batch_size,:]) for i in np.arange(0,len(latent),self.args.batch_size)]
        res = []
        with torch.no_grad():
            for v in latent:
                r = self._generate_batch(v)
                res.extend(r)
        return res


def main():
    args = get_argument()
    model = GRU(args)
    latent = pd.read_csv(args.latent_path,index_col=0)
    generator = Generator(args,model)
    results = generator.generate(latent)
    output_path = os.path.join(args.experiment_dir,"generated.txt") if len(args.output_path) == 0 else args.output_path
    with open(output_path, "w") as f:
        f.write("\n".join(results))


if __name__ == "__main__":
    main()