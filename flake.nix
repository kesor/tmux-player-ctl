{
  description = "tmux-player-ctl";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
    in
    {
      packages.x86_64-linux = {
        default = pkgs.writeScriptBin "tmux-player-ctl" (builtins.readFile ./tmux-player-ctl.py);
      };

      devShells.x86_64-linux.default = pkgs.mkShell {
        packages = with pkgs; [
          python313
          python313Packages.coverage
        ];

        shellHook = ''
          # Run tests from tests/ directory
          alias test="cd tests && python3 -m unittest discover -v"
          alias cov="cd tests && python3 -m coverage run --source=.. -m unittest discover -q && python3 -m coverage report --skip-covered"
        '';
      };
    };
}
