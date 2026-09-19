from flask import Flask, request, jsonify, Response
import requests
import xml.sax.saxutils as saxutils
import json
import math
app = Flask(__name__)
def limpar_numeros_invalidos(obj):
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return 0
        return obj

    if isinstance(obj, dict):
        return {
            chave: limpar_numeros_invalidos(valor)
            for chave, valor in obj.items()
        }

    if isinstance(obj, list):
        return [
            limpar_numeros_invalidos(valor)
            for valor in obj
        ]

    return obj

SERVICOS_MESTRES = {
    "workspace": "Workspace",
    "lighting": "Lighting",
    "replicatedfirst": "ReplicatedFirst",
    "replicatedstorage": "ReplicatedStorage",
    "serverscriptservice": "ServerScriptService",
    "serverstorage": "ServerStorage",
    "startergui": "StarterGui",
    "starterplayer": "StarterPlayer",
    "starterpack": "StarterPack",
    "teams": "Teams",
    "soundservice": "SoundService",
    "httpservice": "HttpService",
    "testservice": "TestService",
    "voicechatservice": "VoiceChatService",
    "localizationservice": "LocalizationService",
    "chat": "Chat"
}

# Lista de propriedades que o Roblox exige estritamente como <bool>
PROPRIEDADES_BOOLEANAS = {
    "IgnoreGuiInset", "Enabled", "Visible", "ResetOnSpawn", "Archivable",
    "Anchored", "CanCollide", "CanTouch", "CanQuery", "CastShadow",
    "Massless", "Locked", "ClipToDeviceSafeArea", "ClipsDescendants",
    "Active", "AutoButtonColor", "Selected", "RichText", "TextScaled",
    "TextWrapped", "ClearTextOnFocus", "MultiLine", "DisplayOrder"
}

# Tabela expandida de Tokens Enum oficiais do Roblox
MAPA_ENUM_NUMERICO = {
    # ScreenOrientation (StarterGui / ScreenGui)
    "LandscapeLeft": 0,
    "LandscapeRight": 1,
    "Portrait": 2,
    "Sensor": 3,
    "LandscapeSensor": 4,

    # Face / NormalId (Decal, Texture, SurfaceGui)
    "Right": 0,
    "Top": 1,
    "Back": 2,
    "Left": 3,
    "Bottom": 4,
    "Front": 5,

    # Fonts
    "Legacy": 0, "Arial": 1, "ArialBold": 2, "SourceSans": 3, "SourceSansBold": 4,
    "SourceSansItalic": 5, "SourceSansLight": 6, "SourceSansSemibold": 7,
    "Bodoni": 8, "Garamond": 9, "Courier": 10, "Animate": 11, "Gotham": 12,
    "GothamSemibold": 13, "GothamBold": 14, "GothamBlack": 15, "FredokaOne": 16,
    "Arcade": 17, "FiraMono": 18, "Roboto": 19, "RobotoCondensed": 20, "RobotoMono": 21,

    # ScaleType / SizeConstraint / AutomaticSize / SortOrder
    "Stretch": 0, "Tile": 1, "Slice": 2, "Fit": 3, "Crop": 4,
    "RelativeXY": 0, "RelativeXX": 1, "RelativeYY": 2, "None": 0,
    "X": 1, "Y": 2, "XY": 3,
    "LayoutOrder": 0, "Name": 1,

    # Material
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512,
    "WoodPlanks": 528, "Marble": 784, "Basalt": 788, "Slate": 800,
    "CrackedLava": 804, "Concrete": 816, "Granite": 832, "Brick": 848,
    "Pebble": 864, "Cobblestone": 880, "Rock": 896, "Sand": 1280,
    "Fabric": 1296, "Ice": 1536, "Glass": 1568, "ForceField": 1584,
    "Foil": 1792, "Metal": 1056, "DiamondPlate": 1072, "CorrodedMetal": 1088,

    # Technology / Lighting
    "Compatibility": 0, "Voxel": 1, "ShadowMap": 2, "Future": 3,

    # SurfaceType / FormFactor / PartType
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, "Universal": 5, "Hinge": 6, "Motor": 7,
    "Ball": 0, "Block": 1, "Cylinder": 2, "Wedge": 3, "CornerWedge": 4,

    # ZIndexBehavior
    "Global": 0,
    "Sibling": 1
}

def converter_cor(valor):
    r, g, b = 0.0, 0.0, 0.0
    if isinstance(valor, dict):
        r = float(valor.get("R", valor.get("r", 0.0)))
        g = float(valor.get("G", valor.get("g", 0.0)))
        b = float(valor.get("B", valor.get("b", 0.0)))
    elif isinstance(valor, (list, tuple)) and len(valor) >= 3:
        r, g, b = float(valor[0]), float(valor[1]), float(valor[2])

    rf = r / 255.0 if r > 1.0 else r
    gf = g / 255.0 if g > 1.0 else g
    bf = b / 255.0 if b > 1.0 else b

    return rf, gf, bf

def tratar_propriedade_individual(nome_prop, valor):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    # 1. TRATAMENTO ESTRITO DE BOOLEANOS (IgnoreGuiInset, Enabled, etc)
    if isinstance(valor, bool) or nome_prop in PROPRIEDADES_BOOLEANAS:
        if isinstance(valor, str):
            val_bool_str = "true" if valor.lower() in ["true", "1", "yes"] else "false"
        else:
            val_bool_str = "true" if bool(valor) is True else "false"
        return f'<bool name="{nome_prop}">{val_bool_str}</bool>'

    # 2. STRINGS E ENUMS (ScreenOrientation, Face, Material, etc)
    if isinstance(valor, str):
        val_limpo = valor.strip()
        
        # Remove prefixo 'Enum.Grupo.Nome' se existir
        if "Enum." in val_limpo:
            val_limpo = val_limpo.split(".")[-1]

        # Mapeamento para token numérico
        if val_limpo in MAPA_ENUM_NUMERICO:
            token_val = MAPA_ENUM_NUMERICO[val_limpo]
            return f'<token name="{nome_prop}">{token_val}</token>'

        # Conteúdo de Asset/Textura
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or val_limpo.startswith("rbxassetid://"):
            return f'<Content name="{nome_prop}"><url>{saxutils.escape(val_limpo)}</url></Content>'

        # String padrão
        return f'<string name="{nome_prop}">{saxutils.escape(val_limpo)}</string>'

    # 3. DICIONÁRIOS / TABELAS (UDim, UDim2, Vector3, Color3, Enums em Tabela)
    if isinstance(valor, dict):
        # Enum vindo em formato de tabela Luau {EnumType = ..., Name = "Sensor"}
        if "Name" in valor:
            nome_enum = str(valor["Name"]).strip()
            if nome_enum in MAPA_ENUM_NUMERICO:
                return f'<token name="{nome_prop}">{MAPA_ENUM_NUMERICO[nome_enum]}</token>'

        # UDim2
        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict) and isinstance(valor.get("Y"), dict):
            xs = float(valor["X"].get("Scale", valor["X"].get("scale", 0)))
            xo = int(valor["X"].get("Offset", valor["X"].get("offset", 0)))
            ys = float(valor["Y"].get("Scale", valor["Y"].get("scale", 0)))
            yo = int(valor["Y"].get("Offset", valor["Y"].get("offset", 0)))
            return f'<UDim2 name="{nome_prop}"><XS>{xs}</XS><XO>{xo}</XO><YS>{ys}</YS><YO>{yo}</YO></UDim2>'

        # UDim (Simples)
        if ("Scale" in valor or "scale" in valor) and ("Offset" in valor or "offset" in valor) and "X" not in valor:
            s = float(valor.get("Scale", valor.get("scale", 0)))
            o = int(valor.get("Offset", valor.get("offset", 0)))
            return f'<UDim name="{nome_prop}"><S>{s}</S><O>{o}</O></UDim>'

        # Vector3
        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'<Vector3 name="{nome_prop}"><X>{float(valor["X"])}</X><Y>{float(valor["Y"])}</Y><Z>{float(valor["Z"])}</Z></Vector3>'

        # Vector2
        if "X" in valor and "Y" in valor and "Z" not in valor:
            return f'<Vector2 name="{nome_prop}"><X>{float(valor["X"])}</X><Y>{float(valor["Y"])}</Y></Vector2>'

        # Color3
        if ("R" in valor or "r" in valor) and ("G" in valor or "g" in valor) and ("B" in valor or "b" in valor):
            rf, gf, bf = converter_cor(valor)
            return f'<Color3 name="{nome_prop}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></Color3>'

    # 4. ARRAYS (CFrame)
    if isinstance(valor, list):
        if len(valor) in [12, 16]:
            return f'''<CoordinateFrame name="{nome_prop}">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 5. NÚMEROS / TOKENS
    if isinstance(valor, float):
        return f'<float name="{nome_prop}">{valor}</float>'

    if isinstance(valor, int):
        # Se for propriedade conhecida de Enum e vier como número direto, envia como token
        if nome_prop in ["ScreenOrientation", "Face", "Material", "Font", "ScaleType", "SortOrder"]:
            return f'<token name="{nome_prop}">{valor}</token>'
        return f'<int name="{nome_prop}">{valor}</int>'

    return ""

def processar_dicionario_propriedades(props_dict):
    xml_props = []
    for k, v in props_dict.items():
        no_xml = tratar_propriedade_individual(k, v)
        if no_xml:
            xml_props.append(f"            {no_xml}")
    return "\n".join(xml_props)

def processar_objetos_xml(TableData):
    xml_output = []
    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", []) or a.get("Objects", [])
                script_code = a.get("Script") or (props.get("Source") if isinstance(props, dict) else None)

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                item_str = f'<Item class="{class_name}" referent="{ref_id}">\n  <Properties>\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'
                props_xml = processar_dicionario_propriedades(props)
                if props_xml:
                    item_str += f"\n{props_xml}"

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    item_str += f'\n    <ProtectedString name="Source">{saxutils.escape(codigo_str)}</ProtectedString>'

                item_str += '\n  </Properties>'

                if children and isinstance(children, list):
                    item_str += processar_objetos_xml(children)

                item_str += '\n</Item>'
                xml_output.append(item_str)

    return "\n".join(xml_output)

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    workspace_props = ""
    servicos_dados_finais = {
        s_nome: {"props": {}, "objects": []} 
        for s_nome in SERVICOS_MESTRES.values() if s_nome != "Workspace"
    }

    if isinstance(part_data_dict, dict):
        for chave_entrada, servico_dados in part_data_dict.items():
            chave_low = str(chave_entrada).strip().lower()
            servico_oficial = SERVICOS_MESTRES.get(chave_low)

            if not servico_oficial:
                continue

            objetos = []
            propriedades_recebidas = {}

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", []) or servico_dados.get("Children", [])
                if "Properties" in servico_dados and isinstance(servico_dados["Properties"], dict):
                    propriedades_recebidas = servico_dados["Properties"]
                else:
                    propriedades_recebidas = {k: v for k, v in servico_dados.items() if k not in ["Objects", "Children"]}

            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_oficial == "Workspace":
                workspace_content = processar_objetos_xml(objetos)
                workspace_props = processar_dicionario_propriedades(propriedades_recebidas)
            else:
                servicos_dados_finais[servico_oficial]["props"].update(propriedades_recebidas)
                servicos_dados_finais[servico_oficial]["objects"] = objetos

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    outros_servicos_list = []
    for s_nome, dados in servicos_dados_finais.items():
        ref_servico = f"RBX_SERVICE_{s_nome.upper()}"
        props_xml = processar_dicionario_propriedades(dados["props"])
        objs_xml = processar_objetos_xml(dados["objects"])

        outros_servicos_list.append(f'''
    <Item class="{s_nome}" referent="{ref_servico}">
        <Properties>
            <string name="Name">{s_nome}</string>
{props_xml}
        </Properties>
{objs_xml}
    </Item>''')

    outros_servicos_str = "".join(outros_servicos_list)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
{workspace_props}
        </Properties>
        {workspace_content}
    </Item>{outros_servicos_str}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)

        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"
        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

import os
import struct
import lz4.block

API_KEY = "xF7CU6YnsE6jGbrKmaxaPaoIlgkPLp5EUCmLrzV3Zxtc43P0ZXlKaGJHY2lPaUpTVXpJMU5pSXNJbXRwWkNJNkluTnBaeTB5TURJeExUQTNMVEV6VkRFNE9qVXhPalE1V2lJc0luUjVjQ0k2SWtwWFZDSjkuZXlKaGRXUWlPaUpTYjJKc2IzaEpiblJsY201aGJDSXNJbWx6Y3lJNklrTnNiM1ZrUVhWMGFHVnVkR2xqWVhScGIyNVRaWEoyYVdObElpd2lZbUZ6WlVGd2FVdGxlU0k2SW5oR04wTlZObGx1YzBVMmFrZGlja3R0WVhoaFVHRnZTV3huYTFCTWNEVkZWVU50VEhKNlZqTmFlSFJqTkROUU1DSXNJbTkzYm1WeVNXUWlPaUl5TURNMU5qVTROelUwSWl3aVpYaHdJam94TnpnNU16VTJNelkzTENKcFlYUWlPakUzT0Rrek5USTNOamNzSW01aVppSTZNVGM0T1RNMU1qYzJOMzAuUXVyaDllaXpRWDZ1M2tyTjBuVVlXSXdQQzd2M0FBZ2ZWYTFkNzQ5TmVlQUZqMGRIdHdEYkd1LTFicTcyT1A0WUQ0YXRIN2FzRm5UU04wY2wzeFlpZkVRV1VIN3ozVk92Q0RvSVR0TE9icVF4VV9tUEU1QmQ5NGtjMTNJbnJhLVJoNUVSMlREakhxam02RDhqekpsUDdMY2VVNnlNZ2pkSk1YaHI1ZVdjUWRIcTU5THpQNGdtTGduT0QwR25Scl9XUUhYODlCMmhHc2FNd19NQXhCQWdwOWtPcUZBTmg4azV6M0o0OExkTUlBRzNxNTZ2RmhKaVBIenhya285d180RVh0UEZIbTFOOFM3Sm9ybGQ5UGVLSkVJeXFSSzZFclcxck1yOG4tbVAtX293aUZGbmFoc3ItWmZLcm93MF95OVVlU1pDMG82ZHYzbUpzUkxpX0ZLUDJn"

if not API_KEY:
    print("[AVISO] ROBLOX_API_KEY não foi configurada.")

def ler_u8(data, pos):
    if pos + 1 > len(data):
        raise ValueError("Fim inesperado do buffer")

    return data[pos], pos + 1


def ler_u32_le(data, pos):
    if pos + 4 > len(data):
        raise ValueError("Fim inesperado do buffer")

    return struct.unpack_from("<I", data, pos)[0], pos + 4


def ler_i32_le(data, pos):
    if pos + 4 > len(data):
        raise ValueError("Fim inesperado do buffer")

    return struct.unpack_from("<i", data, pos)[0], pos + 4


def ler_f32_le(data, pos):
    if pos + 4 > len(data):
        raise ValueError("Fim inesperado do buffer")

    return struct.unpack_from("<f", data, pos)[0], pos + 4


def ler_f64_le(data, pos):
    if pos + 8 > len(data):
        raise ValueError("Fim inesperado do buffer")

    return struct.unpack_from("<d", data, pos)[0], pos + 8


def ler_string(data, pos):
    tamanho, pos = ler_u32_le(data, pos)

    if tamanho > len(data) - pos:
        raise ValueError("String ultrapassa o buffer")

    valor = data[pos:pos + tamanho].decode(
        "utf-8",
        errors="replace"
    )

    return valor, pos + tamanho


# ============================================================
# ZIGZAG / ARRAYS INTERCALADOS
# ============================================================

def zigzag_decode32(valor):
    return (valor >> 1) ^ -(valor & 1)


def decode_interleaved_u32(data, quantidade):
    if quantidade == 0:
        return []

    if len(data) < quantidade * 4:
        raise ValueError("Array intercalado inválido")

    resultado = []

    for i in range(quantidade):

        raw = bytes(
            data[i + j * quantidade]
            for j in range(4)
        )

        resultado.append(
            struct.unpack(">I", raw)[0]
        )

    return resultado


def decode_interleaved_i32(data, quantidade):
    valores = decode_interleaved_u32(
        data,
        quantidade
    )

    return [
        zigzag_decode32(v)
        for v in valores
    ]


def decode_float_array(data, quantidade):
    if quantidade == 0:
        return []

    if len(data) < quantidade * 4:
        raise ValueError("Float array inválido")

    valores = []

    for i in range(quantidade):

        raw = bytes(
            data[i + j * quantidade]
            for j in range(4)
        )

        numero = struct.unpack(
            ">I",
            raw
        )[0]

        valores.append(
            struct.unpack(
                ">f",
                struct.pack(">I", numero)
            )[0]
        )

    return valores


# ============================================================
# LEITOR DE CHUNKS RBXM
# ============================================================

def ler_chunks_rbxm(data):

    if not (
        data.startswith(b"<roblox!")
        or data.startswith(b"<roblox")
    ):
        raise ValueError(
            "Arquivo não possui cabeçalho RBXM"
        )

    # Cabeçalho RBXM normalmente ocupa 32 bytes.
    pos = 32

    chunks = []

    while pos + 16 <= len(data):

        nome_raw = data[pos:pos + 4]
        pos += 4

        compressed_len = struct.unpack_from(
            "<I",
            data,
            pos
        )[0]
        pos += 4

        uncompressed_len = struct.unpack_from(
            "<I",
            data,
            pos
        )[0]
        pos += 4

        # reservado
        pos += 4

        nome = nome_raw.rstrip(
            b"\x00"
        ).decode(
            "ascii",
            errors="ignore"
        )

        if nome == "":
            break

        # ----------------------------------------------------
        # CHUNK NÃO COMPRIMIDO
        # ----------------------------------------------------

        if compressed_len == 0:

            tamanho = uncompressed_len

            if pos + tamanho > len(data):
                raise ValueError(
                    f"Chunk {nome} inválido"
                )

            payload = data[
                pos:pos + tamanho
            ]

            pos += tamanho

        # ----------------------------------------------------
        # CHUNK COMPRIMIDO
        # ----------------------------------------------------

        else:

            if pos + compressed_len > len(data):
                raise ValueError(
                    f"Chunk {nome} comprimido inválido"
                )

            compressed = data[
                pos:pos + compressed_len
            ]

            pos += compressed_len

            payload = None

            # Tenta LZ4
            try:
                payload = lz4.block.decompress(
                    compressed,
                    uncompressed_size=uncompressed_len
                )
            except Exception:
                pass

            # Se não conseguiu, tenta zstandard
            if payload is None:

                if compressed.startswith(
                    b"\x28\xb5\x2f\xfd"
                ):

                    try:
                        import zstandard as zstd

                        payload = (
                            zstd.ZstdDecompressor()
                            .decompress(
                                compressed,
                                max_output_size=uncompressed_len
                            )
                        )

                    except Exception as erro:
                        raise ValueError(
                            f"Não foi possível descompactar "
                            f"chunk {nome}: {erro}"
                        )

            if payload is None:
                raise ValueError(
                    f"Compressão desconhecida "
                    f"no chunk {nome}"
                )

        chunks.append(
            (nome, payload)
        )

        if nome == "END":
            break

    return chunks


# ============================================================
# DECODIFICADOR DE PROPRIEDADES
# ============================================================

def decodificar_prop(
    type_id,
    payload,
    pos,
    quantidade
):

    # --------------------------------------------------------
    # String
    # --------------------------------------------------------

    if type_id == 0x01:

        valores = []

        for _ in range(quantidade):

            valor, pos = ler_string(
                payload,
                pos
            )

            valores.append(valor)

        return valores, pos


    # --------------------------------------------------------
    # Bool
    # --------------------------------------------------------

    if type_id == 0x02:

        if pos + quantidade > len(payload):
            raise ValueError("Bool inválido")

        valores = []

        for i in range(quantidade):
            valores.append(
                payload[pos + i] != 0
            )

        return valores, pos + quantidade


    # --------------------------------------------------------
    # Int32
    # --------------------------------------------------------

    if type_id == 0x03:

        tamanho = quantidade * 4

        raw = payload[
            pos:pos + tamanho
        ]

        valores = decode_interleaved_i32(
            raw,
            quantidade
        )

        return valores, pos + tamanho


    # --------------------------------------------------------
    # Float32
    # --------------------------------------------------------

    if type_id == 0x04:

        tamanho = quantidade * 4

        raw = payload[
            pos:pos + tamanho
        ]

        valores = decode_float_array(
            raw,
            quantidade
        )

        return valores, pos + tamanho


    # --------------------------------------------------------
    # Double
    # --------------------------------------------------------

    if type_id == 0x05:

        valores = []

        for _ in range(quantidade):

            valor, pos = ler_f64_le(
                payload,
                pos
            )

            valores.append(valor)

        return valores, pos


    # --------------------------------------------------------
    # UDim
    # --------------------------------------------------------

    if type_id == 0x06:

        escalas = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        offsets = decode_interleaved_i32(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "Scale": escalas[i],
                "Offset": offsets[i]
            })

        return valores, pos


    # --------------------------------------------------------
    # UDim2
    # --------------------------------------------------------

    if type_id == 0x07:

        sx = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        sy = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        ox = decode_interleaved_i32(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        oy = decode_interleaved_i32(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "X": {
                    "Scale": sx[i],
                    "Offset": ox[i]
                },
                "Y": {
                    "Scale": sy[i],
                    "Offset": oy[i]
                }
            })

        return valores, pos


    # --------------------------------------------------------
    # BrickColor / Token
    # --------------------------------------------------------

    if type_id == 0x0B:

        tamanho = quantidade * 4

        valores = decode_interleaved_u32(
            payload[
                pos:
                pos + tamanho
            ],
            quantidade
        )

        return valores, pos + tamanho


    # --------------------------------------------------------
    # Color3
    # --------------------------------------------------------

    if type_id == 0x0C:

        r = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        g = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        b = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "R": r[i],
                "G": g[i],
                "B": b[i]
            })

        return valores, pos


    # --------------------------------------------------------
    # Vector2
    # --------------------------------------------------------

    if type_id == 0x0D:

        x = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        y = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "X": x[i],
                "Y": y[i]
            })

        return valores, pos


    # --------------------------------------------------------
    # Vector3
    # --------------------------------------------------------

    if type_id == 0x0E:

        x = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        y = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        z = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "X": x[i],
                "Y": y[i],
                "Z": z[i]
            })

        return valores, pos


    # --------------------------------------------------------
    # Token / Enum
    # --------------------------------------------------------

    if type_id == 0x12:

        tamanho = quantidade * 4

        valores = decode_interleaved_u32(
            payload[
                pos:
                pos + tamanho
            ],
            quantidade
        )

        return valores, pos + tamanho


    # --------------------------------------------------------
    # Referent
    # --------------------------------------------------------

    if type_id == 0x13:

        tamanho = quantidade * 4

        raw = payload[
            pos:
            pos + tamanho
        ]

        deltas = decode_interleaved_i32(
            raw,
            quantidade
        )

        valores = []

        atual = 0

        for delta in deltas:

            atual += delta

            if atual == -1:
                valores.append(None)
            else:
                valores.append(atual)

        return valores, pos + tamanho


    # --------------------------------------------------------
    # Vector3int16
    # --------------------------------------------------------

    if type_id == 0x14:

        valores = []

        for _ in range(quantidade):

            if pos + 6 > len(payload):
                raise ValueError(
                    "Vector3int16 inválido"
                )

            x, y, z = struct.unpack_from(
                "<hhh",
                payload,
                pos
            )

            pos += 6

            valores.append({
                "X": x,
                "Y": y,
                "Z": z
            })

        return valores, pos


    # --------------------------------------------------------
    # NumberRange
    # --------------------------------------------------------

    if type_id == 0x17:

        valores = []

        for _ in range(quantidade):

            minimo, pos = ler_f32_le(
                payload,
                pos
            )

            maximo, pos = ler_f32_le(
                payload,
                pos
            )

            valores.append({
                "Min": minimo,
                "Max": maximo
            })

        return valores, pos


    # --------------------------------------------------------
    # Rect
    # --------------------------------------------------------

    if type_id == 0x18:

        x0 = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        y0 = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        x1 = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        y1 = decode_float_array(
            payload[
                pos:
                pos + quantidade * 4
            ],
            quantidade
        )

        pos += quantidade * 4

        valores = []

        for i in range(quantidade):

            valores.append({
                "Min": {
                    "X": x0[i],
                    "Y": y0[i]
                },
                "Max": {
                    "X": x1[i],
                    "Y": y1[i]
                }
            })

        return valores, pos


    # --------------------------------------------------------
    # Color3uint8
    # --------------------------------------------------------

    if type_id == 0x1A:

        if pos + quantidade * 3 > len(payload):
            raise ValueError(
                "Color3uint8 inválido"
            )

        r = payload[
            pos:
            pos + quantidade
        ]

        pos += quantidade

        g = payload[
            pos:
            pos + quantidade
        ]

        pos += quantidade

        b = payload[
            pos:
            pos + quantidade
        ]

        pos += quantidade

        valores = []

        for i in range(quantidade):

            valores.append({
                "R": r[i],
                "G": g[i],
                "B": b[i]
            })

        return valores, pos


    # --------------------------------------------------------
    # Int64
    # --------------------------------------------------------

    if type_id == 0x1B:

        valores = []

        for _ in range(quantidade):

            if pos + 8 > len(payload):
                raise ValueError(
                    "Int64 inválido"
                )

            valor = int.from_bytes(
                payload[pos:pos + 8],
                "big",
                signed=True
            )

            pos += 8

            valores.append(valor)

        return valores, pos


    # --------------------------------------------------------
    # Tipo não conhecido
    # --------------------------------------------------------

    raise ValueError(
        f"Tipo PROP não implementado: "
        f"0x{type_id:02X}"
    )


# ============================================================
# PARSER PRINCIPAL RBXM
# ============================================================

def extrair_instancias_e_nomes_rbxm(
    conteudo_bytes
):

    chunks = ler_chunks_rbxm(
        conteudo_bytes
    )

    # --------------------------------------------------------
    # Todas as classes encontradas
    # --------------------------------------------------------

    classes = {}

    # --------------------------------------------------------
    # INST
    # --------------------------------------------------------

    for nome_chunk, payload in chunks:

        if nome_chunk != "INST":
            continue

        pos = 0

        class_id, pos = ler_u32_le(
            payload,
            pos
        )

        class_name, pos = ler_string(
            payload,
            pos
        )

        object_format, pos = ler_u8(
            payload,
            pos
        )

        quantidade, pos = ler_u32_le(
            payload,
            pos
        )

        tamanho_refs = quantidade * 4

        if pos + tamanho_refs > len(payload):
            continue

        refs_raw = payload[
            pos:
            pos + tamanho_refs
        ]

        pos += tamanho_refs

        refs_delta = decode_interleaved_i32(
            refs_raw,
            quantidade
        )

        referents = []

        atual = 0

        for delta in refs_delta:

            atual += delta

            referents.append(atual)

        classes[class_id] = {
            "ClassName": class_name,
            "Referents": referents,
            "Names": [None] * quantidade
        }


    # --------------------------------------------------------
    # Criar objetos
    # --------------------------------------------------------

    todas = {}

    for class_id, classe in classes.items():

        class_name = classe["ClassName"]

        for referent in classe["Referents"]:

            todas[referent] = {
                "Instance": class_name,

                "Properties": {
                    "Name": class_name,
                    "ClassName": class_name,
                    "Referent": referent
                },

                "Children": {},

                "Script": None
            }


    # --------------------------------------------------------
    # PROP
    # --------------------------------------------------------

    for nome_chunk, payload in chunks:

        if nome_chunk != "PROP":
            continue

        try:

            pos = 0

            class_id, pos = ler_u32_le(
                payload,
                pos
            )

            prop_name, pos = ler_string(
                payload,
                pos
            )

            type_id, pos = ler_u8(
                payload,
                pos
            )

            classe = classes.get(
                class_id
            )

            if not classe:
                continue

            referents = classe[
                "Referents"
            ]

            quantidade = len(
                referents
            )

            valores, pos = decodificar_prop(
                type_id,
                payload,
                pos,
                quantidade
            )

            for i, referent in enumerate(
                referents
            ):

                if referent not in todas:
                    continue

                if i >= len(valores):
                    continue

                valor = valores[i]

                todas[referent][
                    "Properties"
                ][prop_name] = valor

                # --------------------------------------------
                # SOURCE REAL
                # --------------------------------------------

                if prop_name == "Source":

                    if isinstance(
                        valor,
                        str
                    ):

                        todas[referent][
                            "Script"
                        ] = valor

        except Exception as erro:

            print(
                "[RBXM] Erro lendo PROP:",
                erro
            )

            continue


    # --------------------------------------------------------
    # PRNT
    # --------------------------------------------------------

    relacionamentos = []

    for nome_chunk, payload in chunks:

        if nome_chunk != "PRNT":
            continue

        try:

            pos = 0

            version, pos = ler_u8(
                payload,
                pos
            )

            quantidade, pos = ler_u32_le(
                payload,
                pos
            )

            tamanho = quantidade * 4

            child_raw = payload[
                pos:
                pos + tamanho
            ]

            pos += tamanho

            parent_raw = payload[
                pos:
                pos + tamanho
            ]

            child_delta = decode_interleaved_i32(
                child_raw,
                quantidade
            )

            parent_delta = decode_interleaved_i32(
                parent_raw,
                quantidade
            )

            children_refs = []

            atual = 0

            for delta in child_delta:

                atual += delta

                children_refs.append(
                    atual
                )

            parent_refs = []

            atual = 0

            for delta in parent_delta:

                atual += delta

                parent_refs.append(
                    atual
                )

            for child_ref, parent_ref in zip(
                children_refs,
                parent_refs
            ):

                relacionamentos.append(
                    (
                        child_ref,
                        parent_ref
                    )
                )

        except Exception as erro:

            print(
                "[RBXM] Erro lendo PRNT:",
                erro
            )


    # --------------------------------------------------------
    # Montar árvore
    # --------------------------------------------------------

    possui_pai = set()

    for child_ref, parent_ref in relacionamentos:

        child = todas.get(
            child_ref
        )

        parent = todas.get(
            parent_ref
        )

        if not child or not parent:
            continue

        nome = child[
            "Properties"
        ].get(
            "Name",
            child["Instance"]
        )

        chave = nome
        numero = 2

        while chave in parent["Children"]:

            chave = f"{nome}_{numero}"

            numero += 1

        parent["Children"][chave] = child

        possui_pai.add(
            child_ref
        )


    # --------------------------------------------------------
    # Encontrar roots
    # --------------------------------------------------------

    roots = {}

    for referent, instancia in todas.items():

        if referent in possui_pai:
            continue

        nome = instancia[
            "Properties"
        ].get(
            "Name",
            instancia["Instance"]
        )

        chave = nome
        numero = 2

        while chave in roots:

            chave = f"{nome}_{numero}"

            numero += 1

        roots[chave] = instancia


    return roots


# ============================================================
# LIMPAR REFERENTS DA RESPOSTA
# ============================================================

def limpar_referents(obj):

    if not isinstance(obj, dict):
        return obj

    resultado = {}

    for chave, valor in obj.items():

        if chave == "Referent":
            continue

        if chave == "Children":

            resultado[chave] = {
                nome: limpar_referents(
                    filho
                )
                for nome, filho
                in valor.items()
            }

        elif isinstance(valor, dict):

            resultado[chave] = limpar_referents(
                valor
            )

        elif isinstance(valor, list):

            resultado[chave] = [
                limpar_referents(x)
                if isinstance(x, dict)
                else x
                for x in valor
            ]

        else:

            resultado[chave] = valor

    return resultado


# ============================================================
# ROTA /carregarasset
# ============================================================

@app.route(
    "/carregarasset",
    methods=["GET", "POST"]
)
def carregarasset():

    try:

        # ----------------------------------------------------
        # Asset ID
        # ----------------------------------------------------

        body = request.get_json(
            silent=True
        ) or {}

        asset_id = (
            request.args.get("assetId")
            or request.args.get("id")
            or body.get("assetId")
        )

        if not asset_id:

            return jsonify({
                "erro": "Asset ID nao informado"
            }), 400


        asset_id = str(
            asset_id
        ).strip()


        # ----------------------------------------------------
        # API key
        # ----------------------------------------------------

        if not API_KEY:

            return jsonify({
                "erro": "ROBLOX_API_KEY não configurada"
            }), 500


        # ----------------------------------------------------
        # Asset Delivery API
        # ----------------------------------------------------

        roblox_url = (
            "https://apis.roblox.com/"
            "asset-delivery-api/v1/"
            f"assetId/{asset_id}"
        )

        headers = {
            "User-Agent": "Roblox/WinInet",
            "Accept": "*/*",
            "x-api-key": API_KEY
        }

        res = requests.get(
            roblox_url,
            headers=headers,
            timeout=15
        )


        # ----------------------------------------------------
        # Verificar resposta
        # ----------------------------------------------------

        try:

            data = res.json()

        except Exception:

            return jsonify({
                "erro": "Roblox retornou resposta inválida",
                "status": res.status_code,
                "resposta": res.text[:1000]
            }), 502


        if res.status_code >= 400:

            return jsonify({
                "erro": "Roblox recusou o asset",
                "status": res.status_code,
                "detalhes": data
            }), res.status_code


        # ----------------------------------------------------
        # Encontrar download URL
        # ----------------------------------------------------

        download_url = None

        if isinstance(data, list):

            if data:

                item = data[0]

                if (
                    isinstance(item, dict)
                    and item.get("locations")
                ):

                    locations = item[
                        "locations"
                    ]

                    if locations:

                        download_url = (
                            locations[0]
                            .get("location")
                        )

                elif isinstance(item, dict):

                    download_url = item.get(
                        "location"
                    )

        elif isinstance(data, dict):

            if data.get("location"):

                download_url = data[
                    "location"
                ]

            elif data.get("locations"):

                locations = data[
                    "locations"
                ]

                if locations:

                    download_url = (
                        locations[0]
                        .get("location")
                    )


        # ----------------------------------------------------
        # Asset não encontrado
        # ----------------------------------------------------

        if not download_url:

            return jsonify({
                "erro": "Asset nao encontrado",
                "asset_id": asset_id,
                "detalhes": data
            }), 404


        # ----------------------------------------------------
        # Baixar RBXM
        # ----------------------------------------------------

        file_res = requests.get(
            download_url,
            headers={
                "User-Agent": "Roblox/WinInet",
                "Accept": "*/*",
                "Accept-Encoding": "identity"
            },
            timeout=30
        )

        file_res.raise_for_status()

        conteudo_bruto = (
            file_res.content
        )


        # ----------------------------------------------------
        # Resultado
        # ----------------------------------------------------

        services_mestres = {}


        # ====================================================
        # RBXM BINÁRIO
        # ====================================================

        if (
            conteudo_bruto.startswith(
                b"<roblox!"
            )
            or conteudo_bruto.startswith(
                b"<roblox"
            )
        ):

            filhos_reais = (
                extrair_instancias_e_nomes_rbxm(
                    conteudo_bruto
                )
            )

            filhos_reais = limpar_referents(
                filhos_reais
            )

            services_mestres[
                "Workspace"
            ] = {

                "Instance": "Workspace",

                "Properties": {
                    "Name": "Workspace",
                    "ClassName": "Workspace"
                },

                "Children": filhos_reais,

                "Script": None
            }


        # ====================================================
        # XML RBXLX / RBXM XML
        # ====================================================

        else:

            import xml.etree.ElementTree as ET

            try:

                inicio = (
                    conteudo_bruto.find(
                        b"<roblox"
                    )
                )

                if inicio >= 0:

                    fim = (
                        conteudo_bruto.rfind(
                            b"</roblox>"
                        )
                    )

                    if fim >= 0:

                        fim += len(
                            b"</roblox>"
                        )

                        xml_valido = (
                            conteudo_bruto[
                                inicio:fim
                            ]
                        )

                    else:

                        xml_valido = (
                            conteudo_bruto[
                                inicio:
                            ]
                        )

                else:

                    xml_valido = (
                        conteudo_bruto
                    )


                root = ET.fromstring(
                    xml_valido
                )


                def processar_xml(elem):

                    classe = elem.attrib.get(
                        "class",
                        "Folder"
                    )

                    nome = elem.attrib.get(
                        "referent",
                        classe
                    )

                    properties = {
                        "Name": nome,
                        "ClassName": classe
                    }

                    children = {}

                    script = None

                    for child in elem:

                        if child.tag == "Properties":

                            for prop in child:

                                prop_name = (
                                    prop.attrib.get(
                                        "name",
                                        prop.tag
                                    )
                                )

                                valor = (
                                    prop.text
                                    or ""
                                )

                                if prop.tag == "bool":

                                    valor = (
                                        valor.lower()
                                        == "true"
                                    )

                                properties[
                                    prop_name
                                ] = valor

                                if (
                                    prop_name
                                    == "Source"
                                    and isinstance(
                                        valor,
                                        str
                                    )
                                ):

                                    script = valor

                        elif child.tag == "Item":

                            filho = (
                                processar_xml(
                                    child
                                )
                            )

                            filho_nome = (
                                filho[
                                    "Properties"
                                ].get(
                                    "Name",
                                    filho[
                                        "Instance"
                                    ]
                                )
                            )

                            chave = filho_nome
                            numero = 2

                            while chave in children:

                                chave = (
                                    f"{filho_nome}_"
                                    f"{numero}"
                                )

                                numero += 1

                            children[
                                chave
                            ] = filho


                    return {
                        "Instance": classe,
                        "Properties": properties,
                        "Children": children,
                        "Script": script
                    }


                for item in root.findall(
                    "Item"
                ):

                    processado = (
                        processar_xml(
                            item
                        )
                    )

                    nome = (
                        processado["Properties"].get("Name", processado["Instance"])
                    )
                    services_mestres[nome] = processado
                    
            except Exception as erro:
                services_mestres["Workspace"] = {
                    "Instance": "Workspace",
                    "Properties": {
                        "Name": "Workspace",
                        "ClassName": "Workspace"
                    },
                    "Children": {},
                    "Script": None
                }
                print("[XML] Erro:", erro)

        services_mestres = limpar_numeros_invalidos(services_mestres)

        json_final = json.dumps({
            "sucesso": True,
            "asset_id": asset_id,
            "download_url": download_url,
            "services": services_mestres
        }, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

        print("================================")
        print("[DEBUG] JSON gerado com sucesso!")
        print("[DEBUG] Caracteres:", len(json_final))
        print("[DEBUG] Bytes:", len(json_final.encode("utf-8")))
        print("================================")

        return json_final

    except requests.RequestException as erro:
        return jsonify({
            "erro": "Erro ao acessar Roblox",
            "detalhes": str(erro)
        }), 502

    except Exception as erro:
        print("[carregarasset] ERRO:", repr(erro))

        return jsonify({
            "erro_python": str(erro)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
