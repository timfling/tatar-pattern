"""CPU checks for metadata/file loading and validation, no base weights or GPU."""
import json
from pathlib import Path
import tempfile
import unittest
from common import adapter_metadata, meta_unet, sha, write_json

class SmokeTests(unittest.TestCase):
    def test_native_file_preserves_mixed_rank_alpha_and_conv(self):
        import torch
        from diffusers import StableDiffusionXLPipeline
        from safetensors.torch import save_file
        unet = meta_unet()
        for module in unet.modules():
            for name, p in list(module.named_parameters(recurse=False)):
                setattr(module, name, torch.nn.Parameter(torch.zeros(1).expand(p.shape), requires_grad=False))
        targets = [('conv_in', 16, (16, 4, 3, 3), (320, 16, 1, 1)),
                   ('time_embedding.linear_1', 32, (32, 320), (1280, 32))]
        state, mapping = {}, []
        for name, rank, a_shape, b_shape in targets:
            mapping.append(dict(target=name, rank=rank, alpha=rank))
            state[f'unet.{name}.lora_A.weight'] = torch.full(a_shape, 0.0125)
            state[f'unet.{name}.lora_B.weight'] = torch.full(b_shape, 0.025)
        pipe = StableDiffusionXLPipeline(vae=None, text_encoder=None, text_encoder_2=None,
                                        tokenizer=None, tokenizer_2=None, unet=unet, scheduler=None)
        with tempfile.TemporaryDirectory() as tmp:
            save_file(state, str(Path(tmp) / 'synthetic.safetensors'),
                      metadata={'lora_adapter_metadata': json.dumps(adapter_metadata(mapping))})
            pipe.load_lora_weights(tmp, weight_name='synthetic.safetensors', local_files_only=True,
                                   adapter_name='candidate', low_cpu_mem_usage=True)
        pipe.set_adapters(['candidate'], adapter_weights=[1.0])
        for name, rank, _, _ in targets:
            module = unet.get_submodule(name)
            self.assertEqual(module.r['candidate'], rank)
            self.assertEqual(module.scaling['candidate'], 1.0)
            self.assertTrue(torch.equal(module.lora_A['candidate'].weight, state[f'unet.{name}.lora_A.weight']))
        pipe.disable_lora()
        self.assertTrue(unet.conv_in.disable_adapters)
        pipe.enable_lora()
        self.assertFalse(unet.conv_in.disable_adapters)

    def test_result_verifier_rejects_tampering_and_identical_pair(self):
        import hashlib
        from PIL import Image
        from verify_results import verify
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            cases = []
            for enabled in [False, True]:
                name = 'img2img_textured_' + ('on' if enabled else 'off')
                image = Image.new('RGB', (1024, 1024), (50 if enabled else 100, 120, 200))
                image.save(folder / (name + '.png'))
                cases.append(dict(name=name, png=name + '.png', status='SAVED', sha256=sha(folder / (name + '.png')),
                                  pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(), parameters={'prompt': 'tptrx'},
                                  seed=20261008, timesteps=[5], denoising_steps=1, inference_seconds=1, peak_allocated_bytes=1))
            run = dict(status='INFERENCE_COMPLETE_REVIEW_REQUIRED', suite='pair', cases=cases)
            write_json(folder / 'run.json', run)
            self.assertEqual(verify(folder)['status'], 'TECHNICAL_CHECKS_PASS')
            cases[1]['parameters']['prompt'] = 'changed'
            write_json(folder / 'run.json', run)
            with self.assertRaisesRegex(ValueError, 'settings differ'):
                verify(folder)
            cases[1]['parameters']['prompt'] = 'tptrx'
            cases[1].update(png=cases[0]['png'], sha256=cases[0]['sha256'], pixel_sha256=cases[0]['pixel_sha256'])
            write_json(folder / 'run.json', run)
            with self.assertRaisesRegex(ValueError, 'Identical'):
                verify(folder)
            (folder / cases[0]['png']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                verify(folder)

if __name__ == '__main__':
    unittest.main()
